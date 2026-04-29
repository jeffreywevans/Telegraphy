from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, NamedTuple

from ._constants import (
    CHARACTER_AVAILABILITY_KEY,
    PARTNER_DISTRIBUTIONS_KEY,
    PROMPT_LIST_KEYS,
    SETTING_AVAILABILITY_KEY,
)
from .availability_validation import (
    has_date_overlap,
    validate_availability_rows,
)
from .partner_models import (
    LegacyPartnerIndex,
    parse_partner_distribution_payload,
    require_keys,
)

ANY_TITLE_TOKEN_PATTERN = re.compile(r"@(?P<key>[A-Za-z_]\w*)\b")
EXPECTED_GENERATED_FIELD_KEYS = {
    "title",
    "protagonist",
    "secondary_character",
    "time_period",
    "setting",
    "weather",
    "central_conflict",
    "inciting_pressure",
    "ending_type",
    "style_guidance",
    "sexual_content_level",
    "sexual_partner",
    "sexual_scene_tags",
    "word_count_target",
}
MAX_SEXUAL_SCENE_TAG_GROUPS = 10
PROMPT_LIST_KEYS_SET = frozenset(PROMPT_LIST_KEYS)
ENTITY_AVAILABILITY_KEYS = frozenset({CHARACTER_AVAILABILITY_KEY, SETTING_AVAILABILITY_KEY})


class ValidatedStoryData(NamedTuple):
    character_availability: list[tuple[str, date, date]]
    setting_availability: list[tuple[str, date, date]]
    date_start: date
    date_end: date
    partner_distributions: LegacyPartnerIndex


def _validate_string_list(section_name: str, key: str, values: Any) -> None:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{section_name}.{key} must be a non-empty list")
    for idx, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{section_name}.{key}[{idx}] must be a non-empty string")


def _validate_no_duplicate_strings(section_name: str, key: str, values: list[str]) -> None:
    seen: dict[str, int] = {}
    for idx, value in enumerate(values):
        normalized = value.strip().casefold()
        if normalized in seen:
            first_idx = seen[normalized]
            raise ValueError(
                f"{section_name}.{key} contains duplicate value at index {idx} "
                f"(first seen at index {first_idx})"
            )
        seen[normalized] = idx


def _validate_title_tokens(values: list[str]) -> None:
    allowed = {"protagonist", "setting", "time_period"}
    for idx, value in enumerate(values):
        for token in ANY_TITLE_TOKEN_PATTERN.findall(value):
            if token not in allowed:
                raise ValueError(
                    f"titles.titles[{idx}] contains unsupported token '@{token}'"
                )


def _validate_prompt_lists(prompts: dict[str, Any]) -> None:
    require_keys("prompts", prompts, PROMPT_LIST_KEYS_SET)
    for key in PROMPT_LIST_KEYS:
        _validate_string_list("prompts", key, prompts[key])
        _validate_no_duplicate_strings("prompts", key, prompts[key])


def _validate_titles(titles: dict[str, Any]) -> None:
    require_keys("titles", titles, {"titles"})
    _validate_string_list("titles", "titles", titles["titles"])
    _validate_no_duplicate_strings("titles", "titles", titles["titles"])
    _validate_title_tokens(titles["titles"])


def _validate_entities(
    entities: dict[str, Any],
) -> tuple[list[tuple[str, date, date]], list[tuple[str, date, date]]]:
    require_keys("entities", entities, ENTITY_AVAILABILITY_KEYS)
    character_rows = validate_availability_rows(
        "entities", CHARACTER_AVAILABILITY_KEY, entities[CHARACTER_AVAILABILITY_KEY]
    )
    setting_rows = validate_availability_rows(
        "entities", SETTING_AVAILABILITY_KEY, entities[SETTING_AVAILABILITY_KEY]
    )
    return character_rows, setting_rows


def _validate_config_versions(config: dict[str, Any]) -> None:
    if not isinstance(config["schema_version"], int) or config["schema_version"] < 1:
        raise ValueError("config.schema_version must be an integer >= 1")
    if not isinstance(config["dataset_version"], str) or not config["dataset_version"].strip():
        raise ValueError("config.dataset_version must be a non-empty string")


def _parse_and_validate_config_dates(config: dict[str, Any]) -> tuple[date, date]:
    try:
        start = date.fromisoformat(str(config["date_start"]))
        end = date.fromisoformat(str(config["date_end"]))
    except ValueError as exc:
        raise ValueError("config date_start/date_end must be ISO dates (YYYY-MM-DD)") from exc
    if start > end:
        raise ValueError("config.date_start must be <= config.date_end")
    return start, end


def _validate_config_date_overlap(
    character_rows: list[tuple[str, date, date]],
    setting_rows: list[tuple[str, date, date]],
    start: date,
    end: date,
) -> None:
    if not has_date_overlap(character_rows, start, end):
        raise ValueError(
            f"config date range has no overlap with entities.{CHARACTER_AVAILABILITY_KEY}"
        )
    if not has_date_overlap(setting_rows, start, end):
        raise ValueError(
            f"config date range has no overlap with entities.{SETTING_AVAILABILITY_KEY}"
        )


def _validate_sexual_content_weights(config: dict[str, Any]) -> None:
    _validate_string_list("config", "sexual_content_options", config["sexual_content_options"])
    weights = config["sexual_content_weights"]
    if not isinstance(weights, list) or not weights:
        raise ValueError("config.sexual_content_weights must be a non-empty list")
    if len(weights) != len(config["sexual_content_options"]):
        raise ValueError("config sexual_content_options/weights must be the same length")
    for idx, value in enumerate(weights):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"config.sexual_content_weights[{idx}] must be a real number")
        if not math.isfinite(value):
            raise ValueError(f"config.sexual_content_weights[{idx}] must be finite")
        if value < 0:
            raise ValueError(f"config.sexual_content_weights[{idx}] must be non-negative")
    if sum(weights) <= 0:
        raise ValueError("config.sexual_content_weights must sum to > 0")


def _validate_word_count_targets(config: dict[str, Any]) -> None:
    targets = config["word_count_targets"]
    if not isinstance(targets, list) or not targets:
        raise ValueError("config.word_count_targets must be a non-empty list")
    for idx, value in enumerate(targets):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"config.word_count_targets[{idx}] must be a positive integer")


def _validate_sexual_scene_tag_groups(config: dict[str, Any]) -> None:
    groups = config["sexual_scene_tag_groups"]
    if not isinstance(groups, dict) or not groups:
        raise ValueError("config.sexual_scene_tag_groups must be a non-empty object")
    if len(groups) < 2:
        raise ValueError("config.sexual_scene_tag_groups must contain at least 2 groups")
    if len(groups) > MAX_SEXUAL_SCENE_TAG_GROUPS:
        raise ValueError(
            "config.sexual_scene_tag_groups must contain at most "
            f"{MAX_SEXUAL_SCENE_TAG_GROUPS} groups"
        )

    for group_name, tags in groups.items():
        if not isinstance(group_name, str) or not group_name.strip():
            raise ValueError("config.sexual_scene_tag_groups keys must be non-empty strings")
        _validate_string_list("config", f"sexual_scene_tag_groups.{group_name}", tags)
        _validate_no_duplicate_strings("config", f"sexual_scene_tag_groups.{group_name}", tags)


def _validate_sexual_scene_tag_count_weights(config: dict[str, Any]) -> None:
    raw_weights = config["sexual_scene_tag_count_weights"]
    if not isinstance(raw_weights, dict) or not raw_weights:
        raise ValueError("config.sexual_scene_tag_count_weights must be a non-empty object")

    group_count = len(config["sexual_scene_tag_groups"])
    weight_sum = 0.0
    for raw_count, weight in raw_weights.items():
        count = _parse_positive_weight_count(raw_count)
        if count > group_count:
            raise ValueError(
                "config.sexual_scene_tag_count_weights keys must not exceed the "
                "available sexual_scene_tag_groups count"
            )
        weight_sum += _coerce_non_negative_finite_weight(weight)

    if weight_sum <= 0:
        raise ValueError("config.sexual_scene_tag_count_weights values must sum to > 0")


def _parse_positive_weight_count(raw_count: Any) -> int:
    error_message = (
        "config.sexual_scene_tag_count_weights keys must be positive integers, "
        f"got {raw_count!r}"
    )
    try:
        count = int(raw_count)
    except (TypeError, ValueError) as exc:
        raise ValueError(error_message) from exc
    if str(count) != str(raw_count) or count <= 0:
        raise ValueError(error_message)
    return count


def _coerce_non_negative_finite_weight(weight: Any) -> float:
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise ValueError("config.sexual_scene_tag_count_weights values must be real numbers")
    if not math.isfinite(weight):
        raise ValueError("config.sexual_scene_tag_count_weights values must be finite")
    if weight < 0:
        raise ValueError("config.sexual_scene_tag_count_weights values must be non-negative")
    return float(weight)


def _validate_ordered_keys(config: dict[str, Any]) -> None:
    ordered_keys = config["ordered_keys"]
    if not isinstance(ordered_keys, list) or not ordered_keys:
        raise ValueError("config.ordered_keys must be a non-empty list")
    if len(set(ordered_keys)) != len(ordered_keys):
        raise ValueError("config.ordered_keys must not contain duplicates")
    for idx, key in enumerate(ordered_keys):
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"config.ordered_keys[{idx}] must be a non-empty string")
    ordered_key_set = set(ordered_keys)
    missing = sorted(EXPECTED_GENERATED_FIELD_KEYS - ordered_key_set)
    extra = sorted(ordered_key_set - EXPECTED_GENERATED_FIELD_KEYS)
    if missing or extra:
        problems: list[str] = []
        if missing:
            problems.append(f"missing expected keys: {', '.join(missing)}")
        if extra:
            problems.append(f"unexpected keys: {', '.join(extra)}")
        raise ValueError(f"config.ordered_keys mismatch: {'; '.join(problems)}")


def _validate_writing_preamble(config: dict[str, Any]) -> None:
    if not isinstance(config["writing_preamble"], str) or not config["writing_preamble"].strip():
        raise ValueError("config.writing_preamble must be a non-empty string")


def _validate_partner_distributions(
    partner_payload: dict[str, Any],
    *,
    config_start: date,
    config_end: date,
    character_rows: list[tuple[str, date, date]],
) -> LegacyPartnerIndex:
    dataset = parse_partner_distribution_payload(
        partner_payload,
        config_start=config_start,
        config_end=config_end,
        character_rows=character_rows,
        partner_distributions_key=PARTNER_DISTRIBUTIONS_KEY,
    )
    return dataset.to_legacy_index()


def validate_story_data(
    titles: dict[str, Any],
    entities: dict[str, Any],
    prompts: dict[str, Any],
    config: dict[str, Any],
    partner_distributions: dict[str, Any],
) -> ValidatedStoryData:
    """Validate raw dataset payloads and return normalized availability metadata."""
    _validate_titles(titles)
    character_rows, setting_rows = _validate_entities(entities)

    _validate_prompt_lists(prompts)

    require_keys(
        "config",
        config,
        {
            "schema_version",
            "dataset_version",
            "date_start",
            "date_end",
            "sexual_content_options",
            "sexual_content_weights",
            "sexual_scene_tag_groups",
            "sexual_scene_tag_count_weights",
            "word_count_targets",
            "ordered_keys",
            "writing_preamble",
        },
    )
    _validate_config_versions(config)
    start, end = _parse_and_validate_config_dates(config)
    _validate_config_date_overlap(character_rows, setting_rows, start, end)
    _validate_sexual_content_weights(config)
    _validate_sexual_scene_tag_groups(config)
    _validate_sexual_scene_tag_count_weights(config)
    _validate_word_count_targets(config)
    _validate_ordered_keys(config)
    _validate_writing_preamble(config)
    partner_distribution_index = _validate_partner_distributions(
        partner_distributions,
        config_start=start,
        config_end=end,
        character_rows=character_rows,
    )

    return ValidatedStoryData(
        character_availability=character_rows,
        setting_availability=setting_rows,
        date_start=start,
        date_end=end,
        partner_distributions=partner_distribution_index,
    )
