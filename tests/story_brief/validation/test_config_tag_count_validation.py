from __future__ import annotations

import pytest

from telegraphy.story_brief.schema_validation_config import (
    _parse_non_negative_weight_count,
    validate_sexual_scene_tag_count_weights_by_presence,
    validate_sexual_scene_tag_group_presence_rules,
)


@pytest.mark.parametrize(
    ("raw_count", "minimum", "expected"),
    [(0, 0, 0), (2, 0, 2), (1, 1, 1), ("0", 0, 0), ("2", 1, 2)],
)
def test_parse_weight_count_accepts_integer_and_string_counts(
    raw_count: int | str, minimum: int, expected: int
) -> None:
    assert _parse_non_negative_weight_count(raw_count, "count keys", minimum) == expected


@pytest.mark.parametrize("raw_count", [1.0, None, [], {}])
def test_parse_weight_count_rejects_other_types(raw_count: object) -> None:
    with pytest.raises(ValueError) as exc_info:
        _parse_non_negative_weight_count(raw_count, "count keys")

    assert str(exc_info.value) == f"count keys must be non-negative integers, got {raw_count!r}"


@pytest.mark.parametrize(
    ("raw_count", "minimum", "label"),
    [(-1, 0, "non-negative"), (0, 1, "positive"), ("0", 1, "positive")],
)
def test_parse_weight_count_rejects_counts_below_minimum(
    raw_count: int | str, minimum: int, label: str
) -> None:
    with pytest.raises(ValueError) as exc_info:
        _parse_non_negative_weight_count(raw_count, "count keys", minimum)

    assert str(exc_info.value) == f"count keys must be {label} integers, got {raw_count!r}"


@pytest.mark.parametrize("raw_weights", [None, [], "invalid", {}])
def test_tag_count_weights_rejects_missing_or_invalid_presence_weights(raw_weights: object) -> None:
    config = {
        "sexual_scene_tag_groups": {"tone": ["tender"], "location": ["home"]},
        "sexual_content_presence_options": ["none"],
        "sexual_scene_tag_count_weights_by_presence": {"none": raw_weights},
    }

    with pytest.raises(ValueError) as exc_info:
        validate_sexual_scene_tag_count_weights_by_presence(config)

    assert str(exc_info.value) == (
        "config.sexual_scene_tag_count_weights_by_presence.none must be a non-empty object"
    )


@pytest.mark.parametrize("required_by_presence", [None, [], "invalid"])
def test_presence_rules_rejects_non_object_required_mapping(required_by_presence: object) -> None:
    config = {
        "sexual_scene_tag_groups": {"tone": ["tender"], "location": ["home"]},
        "sexual_scene_required_tag_groups_by_presence": required_by_presence,
        "sexual_scene_optional_tag_groups": [],
    }

    with pytest.raises(ValueError) as exc_info:
        validate_sexual_scene_tag_group_presence_rules(config)

    assert str(exc_info.value) == (
        "config.sexual_scene_required_tag_groups_by_presence must be an object"
    )


@pytest.mark.parametrize("groups", [None, "tone", {"tone": True}, ("tone",)])
def test_presence_rules_rejects_non_list_required_groups(groups: object) -> None:
    config = {
        "sexual_scene_tag_groups": {"tone": ["tender"], "location": ["home"]},
        "sexual_content_presence_options": ["none"],
        "sexual_scene_required_tag_groups_by_presence": {"none": groups},
        "sexual_scene_optional_tag_groups": [],
        "sexual_scene_tag_count_weights_by_presence": {"none": {"0": 1.0}},
    }

    with pytest.raises(ValueError) as exc_info:
        validate_sexual_scene_tag_group_presence_rules(config)

    assert str(exc_info.value) == (
        "config.sexual_scene_required_tag_groups_by_presence.none must be a list"
    )
