from __future__ import annotations

from typing import cast

import pytest

from telegraphy.story_brief.generation import build_sexual_scene_tag_count_distribution
from telegraphy.story_brief.story_data import StoryData


@pytest.mark.parametrize(
    ("groups", "minimum_count"),
    [((), 1), (("tone",), 1), (("tone", "location"), 3)],
)
def test_tag_count_distribution_rejects_unsatisfiable_counts(
    groups: tuple[str, ...], minimum_count: int
) -> None:
    data = cast(StoryData, {"sexual_scene_tag_count_weights_by_presence": {"full": {3: 1.0}}})

    with pytest.raises(ValueError) as exc_info:
        build_sexual_scene_tag_count_distribution(
            groups, data, sexual_content_presence="full", minimum_count=minimum_count
        )

    assert str(exc_info.value) == (
        "No valid sexual scene tag count options remain after filtering "
        "configured counts against available sexual scene tag groups "
        f"(max supported count: {len(groups)})"
    )


@pytest.mark.parametrize("raw_count", [True, False, 1.0, 1.5])
def test_tag_count_distribution_rejects_boolean_and_float_keys(raw_count: object) -> None:
    data = cast(
        StoryData, {"sexual_scene_tag_count_weights_by_presence": {"full": {raw_count: 1.0}}}
    )

    with pytest.raises(TypeError, match="keys must be integers, not booleans or floats"):
        build_sexual_scene_tag_count_distribution(("tone",), data, "full")


@pytest.mark.parametrize(("raw_count", "cause_type"), [("invalid", ValueError), (None, TypeError)])
def test_tag_count_distribution_reports_unconvertible_keys(
    raw_count: object, cause_type: type[Exception]
) -> None:
    data = cast(
        StoryData, {"sexual_scene_tag_count_weights_by_presence": {"full": {raw_count: 1.0}}}
    )

    with pytest.raises(ValueError) as exc_info:
        build_sexual_scene_tag_count_distribution(("tone",), data, "full")

    assert str(exc_info.value) == f"invalid sexual scene tag count key: {raw_count!r}"
    assert isinstance(exc_info.value.__cause__, cause_type)


@pytest.mark.parametrize("raw_weight", [True, False])
def test_tag_count_distribution_rejects_boolean_weights(raw_weight: bool) -> None:
    data = cast(
        StoryData, {"sexual_scene_tag_count_weights_by_presence": {"full": {1: raw_weight}}}
    )

    with pytest.raises(
        TypeError, match="weight for sexual scene tag count 1 must be numeric, not bool"
    ):
        build_sexual_scene_tag_count_distribution(("tone",), data, "full")


@pytest.mark.parametrize(("raw_weight", "cause_type"), [("invalid", ValueError), (None, TypeError)])
def test_tag_count_distribution_reports_unconvertible_weights(
    raw_weight: object, cause_type: type[Exception]
) -> None:
    data = cast(
        StoryData, {"sexual_scene_tag_count_weights_by_presence": {"full": {1: raw_weight}}}
    )

    with pytest.raises(ValueError) as exc_info:
        build_sexual_scene_tag_count_distribution(("tone",), data, "full")

    assert str(exc_info.value) == f"invalid weight for sexual scene tag count 1: {raw_weight!r}"
    assert isinstance(exc_info.value.__cause__, cause_type)
