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
    PartnerDistributionDataset,
    parse_partner_distribution_payload,
    require_keys,
)

ANY_TITLE_TOKEN_PATTERN = re.compile(r"@(?P<key>[A-Za-z_]\w*)\b")
_ALLOWED_TITLE_TOKENS = frozenset({"protagonist", "setting", "time_period"})
_MISSING_TITLE_AT_PATTERN = re.compile(
    rf"(?<!@)\b(?P<key>{'|'.join(re.escape(t) for t in sorted(_ALLOWED_TITLE_TOKENS))})\b"
)
CONFIG_REQUIRED_KEYS = frozenset({
    "schema_version",
    "dataset_version",
    "date_start",
    "date_end",
    "sexual_content_presence_options",
    "sexual_content_presence_weights",
    "sexual_content_story_role_options",
    "sexual_content_story_role_weights",
    "sexual_scene_tag_groups",
    "sexual_scene_tag_count_weights_by_presence",
    "sexual_scene_required_tag_groups_by_presence",
    "sexual_scene_optional_tag_groups",
    "word_count_targets",
    "ordered_keys",
    "writing_preamble",
})

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
UNSUPPORTED_CONFIG_ALIAS_KEYS = (
    "sexual_content_options",
    "sexual_content_weights",
    "sexual_scene_tag_count_weights",
)
UNSUPPORTED_CONFIG_ALIAS_ERROR_PREFIX = (
    "The following config keys are no longer supported; "
    "use canonical fields instead: "
)
PROMPT_LIST_KEYS_SET = frozenset(PROMPT_LIST_KEYS)
OPTIONAL_PROMPT_KEYS = frozenset({"weather_comment"})
ENTITY_AVAILABILITY_KEYS = frozenset({CHARACTER_AVAILABILITY_KEY, SETTING_AVAILABILITY_KEY})


class ValidatedStoryData(NamedTuple):
    character_availability: list[tuple[str, date, date]]
    setting_availability: list[tuple[str, date, date]]
    date_start: date
    date_end: date
    normalized_config: dict[str, Any]
    partner_distributions: PartnerDistributionDataset


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
    for idx, value in enumerate(values):
        for token in ANY_TITLE_TOKEN_PATTERN.findall(value):
            if token not in _ALLOWED_TITLE_TOKENS:
                raise ValueError(
                    f"titles.titles[{idx}] contains unsupported token '@{token}'"
                )

        bare_tokens = sorted(
            {match.group("key") for match in _MISSING_TITLE_AT_PATTERN.finditer(value)}
        )
        if bare_tokens:
            raise ValueError(
                f"titles.titles[{idx}] appears to reference token(s) without '@': "
                f"{', '.join(bare_tokens)}"
            )


def _validate_prompt_lists(prompts: dict[str, Any]) -> None:
    require_keys("prompts", prompts, PROMPT_LIST_KEYS_SET)
    unexpected = sorted(set(prompts) - (PROMPT_LIST_KEYS_SET | OPTIONAL_PROMPT_KEYS))
    if unexpected:
        raise ValueError(f"prompts: unexpected keys: {', '.join(unexpected)}")
    for key in PROMPT_LIST_KEYS:
        _validate_string_list("prompts", key, prompts[key])
        _validate_no_duplicate_strings("prompts", key, prompts[key])
    if "weather_comment" in prompts and (
        not isinstance(prompts["weather_comment"], str) or not prompts["weather_comment"].strip()
    ):
        raise ValueError("prompts.weather_comment must be a non-empty string when provided")


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


def _validate_non_negative_real_weights(
    weights: Any,
    options: list[str],
    *,
    list_error: str,
    length_error: str,
    item_field_prefix: str,
    sum_error: str,
) -> None:
    if not isinstance(weights, list) or not weights:
        raise ValueError(list_error)
    if len(weights) != len(options):
        raise ValueError(length_error)

    for idx, value in enumerate(weights):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{item_field_prefix}[{idx}] must be a real number")
        if not math.isfinite(value):
            raise ValueError(f"{item_field_prefix}[{idx}] must be finite")
        if value < 0:
            raise ValueError(f"{item_field_prefix}[{idx}] must be non-negative")

    if sum(weights) <= 0:
        raise ValueError(sum_error)


def _validate_sexual_content_weights(config: dict[str, Any]) -> None:
    _validate_string_list(
        "config", "sexual_content_presence_options", config["sexual_content_presence_options"]
    )
    _validate_string_list(
        "config",
        "sexual_content_story_role_options",
        config["sexual_content_story_role_options"],
    )

    presence_options = config["sexual_content_presence_options"]
    _validate_non_negative_real_weights(
        config["sexual_content_presence_weights"],
        presence_options,
        list_error="config.sexual_content_presence_weights must be a non-empty list",
        length_error=(
            "config sexual_content_presence_options/"
            "sexual_content_presence_weights must be the same length"
        ),
        item_field_prefix="config.sexual_content_presence_weights",
        sum_error="config.sexual_content_presence_weights must sum to > 0",
    )

    _validate_non_negative_real_weights(
        config["sexual_content_story_role_weights"],
        config["sexual_content_story_role_options"],
        list_error="config.sexual_content_story_role_weights must be a non-empty list",
        length_error=(
            "config sexual_content_story_role_options/"
            "sexual_content_story_role_weights must be the same length"
        ),
        item_field_prefix="config.sexual_content_story_role_weights",
        sum_error="config.sexual_content_story_role_weights must sum to > 0",
    )


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


def _validate_sexual_scene_tag_count_weights_by_presence(config: dict[str, Any]) -> None:
    raw_by_presence = config["sexual_scene_tag_count_weights_by_presence"]
    if not isinstance(raw_by_presence, dict) or not raw_by_presence:
        raise ValueError(
            "config.sexual_scene_tag_count_weights_by_presence must be a non-empty object"
        )

    group_count = len(config["sexual_scene_tag_groups"])
    min_count = 0
    for presence in config["sexual_content_presence_options"]:
        raw_weights = raw_by_presence.get(presence)
        if not isinstance(raw_weights, dict) or not raw_weights:
            raise ValueError(
                "config.sexual_scene_tag_count_weights_by_presence."
                f"{presence} must be a non-empty object"
            )

        weight_sum = 0.0
        for raw_count, weight in raw_weights.items():
            count = _parse_non_negative_weight_count(
                raw_count,
                field_name=f"sexual_scene_tag_count_weights_by_presence.{presence} keys",
                min_count=min_count,
            )
            if count > group_count:
                raise ValueError(
                    f"sexual_scene_tag_count_weights_by_presence.{presence} keys must not exceed "
                    "the available sexual_scene_tag_groups count"
                )
            weight_sum += _coerce_non_negative_finite_weight(
                weight,
                field_name=f"sexual_scene_tag_count_weights_by_presence.{presence} values",
            )
        if weight_sum <= 0:
            raise ValueError(
                f"sexual_scene_tag_count_weights_by_presence.{presence} values must sum to > 0"
            )


def _validate_sexual_scene_tag_group_presence_rules(config: dict[str, Any]) -> None:
    group_names = set(config["sexual_scene_tag_groups"])
    required_by_presence = config["sexual_scene_required_tag_groups_by_presence"]
    optional_groups = config["sexual_scene_optional_tag_groups"]

    if not isinstance(required_by_presence, dict):
        raise ValueError("config.sexual_scene_required_tag_groups_by_presence must be an object")
    if not isinstance(optional_groups, list):
        raise ValueError("config.sexual_scene_optional_tag_groups must be a list")
    if optional_groups:
        _validate_string_list("config", "sexual_scene_optional_tag_groups", optional_groups)
        _validate_no_duplicate_strings(
            "config",
            "sexual_scene_optional_tag_groups",
            optional_groups,
        )

    unknown_optional = sorted(group for group in optional_groups if group not in group_names)
    if unknown_optional:
        raise ValueError(
            "config.sexual_scene_optional_tag_groups contains unknown groups: "
            + ", ".join(unknown_optional)
        )

    presence_options = set(config["sexual_content_presence_options"])
    unknown_presence = sorted(
        presence for presence in required_by_presence if presence not in presence_options
    )
    if unknown_presence:
        raise ValueError(
            "config.sexual_scene_required_tag_groups_by_presence contains unknown presence "
            f"options: {', '.join(unknown_presence)}"
        )

    for presence, groups in required_by_presence.items():
        if not isinstance(groups, list):
            raise ValueError(
                "config.sexual_scene_required_tag_groups_by_presence."
                f"{presence} must be a list"
            )
        if groups:
            _validate_string_list(
                "config", f"sexual_scene_required_tag_groups_by_presence.{presence}", groups
            )
            _validate_no_duplicate_strings(
                "config", f"sexual_scene_required_tag_groups_by_presence.{presence}", groups
            )

        if presence == "none" and len(groups) > 1:
            tag_count_weights = config["sexual_scene_tag_count_weights_by_presence"][presence]
            positive_tag_counts = [
                int(count)
                for count, weight in tag_count_weights.items()
                if weight > 0 and int(count) > 0
            ]
            max_allowed = max(positive_tag_counts, default=0)
            if len(groups) > max_allowed:
                raise ValueError(
                    f"config.sexual_scene_required_tag_groups_by_presence.{presence} "
                    f"requires {len(groups)} groups, but "
                    f"config.sexual_scene_tag_count_weights_by_presence.{presence} "
                    f"allows as few as {max_allowed} tags"
                )

        unknown_required = sorted(group for group in groups if group not in group_names)
        if unknown_required:
            raise ValueError(
                "config.sexual_scene_required_tag_groups_by_presence."
                f"{presence} contains unknown groups: {', '.join(unknown_required)}"
            )

    required_presence_options = set(config["sexual_scene_tag_count_weights_by_presence"])
    missing_presence = sorted(required_presence_options - set(required_by_presence))
    if missing_presence:
        presence_display_aliases = {
            "off_page": "fade_to_black",
            "on_page_brief": "suggestive",
            "on_page_full": "explicit",
        }
        missing_presence_display = sorted(
            presence_display_aliases.get(presence, presence) for presence in missing_presence
        )
        raise ValueError(
            "config.sexual_scene_required_tag_groups_by_presence is missing "
            f"required presence options: {', '.join(missing_presence_display)}"
        )

def _parse_non_negative_weight_count(
    raw_count: Any,
    field_name: str,
    min_count: int = 0,
) -> int:
    minimum_label = "positive" if min_count > 0 else "non-negative"
    error_message = f"{field_name} must be {minimum_label} integers, got {raw_count!r}"
    try:
        count = int(raw_count)
    except (TypeError, ValueError) as exc:
        raise ValueError(error_message) from exc
    if str(count) != str(raw_count) or count < min_count:
        raise ValueError(error_message)
    return count


def _coerce_non_negative_finite_weight(weight: Any, field_name: str = "weight") -> float:
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise ValueError(f"{field_name} must be real numbers")
    if not math.isfinite(weight):
        raise ValueError(f"{field_name} must be finite")
    if weight < 0:
        raise ValueError(f"{field_name} must be non-negative")
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
) -> PartnerDistributionDataset:
    dataset = parse_partner_distribution_payload(
        partner_payload,
        config_start=config_start,
        config_end=config_end,
        character_rows=character_rows,
        partner_distributions_key=PARTNER_DISTRIBUTIONS_KEY,
    )
    return dataset


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized config without mutating caller input."""
    normalized = dict(config)

    present_unsupported_aliases = [
        key for key in UNSUPPORTED_CONFIG_ALIAS_KEYS if key in normalized
    ]
    if present_unsupported_aliases:
        joined = ", ".join(sorted(present_unsupported_aliases))
        raise ValueError(f"{UNSUPPORTED_CONFIG_ALIAS_ERROR_PREFIX}{joined}")

    if "sexual_content_story_role_options" not in normalized:
        normalized["sexual_content_story_role_options"] = ["incidental"]
        normalized["sexual_content_story_role_weights"] = [1.0]
    normalized.setdefault("sexual_scene_optional_tag_groups", [])
    return normalized


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
    normalized_config = _normalize_config(config)

    require_keys("config", normalized_config, CONFIG_REQUIRED_KEYS)
    _validate_config_versions(normalized_config)
    start, end = _parse_and_validate_config_dates(normalized_config)
    _validate_config_date_overlap(character_rows, setting_rows, start, end)
    _validate_sexual_content_weights(normalized_config)
    _validate_sexual_scene_tag_groups(normalized_config)
    _validate_sexual_scene_tag_count_weights_by_presence(normalized_config)
    _validate_sexual_scene_tag_group_presence_rules(normalized_config)
    _validate_word_count_targets(normalized_config)
    _validate_ordered_keys(normalized_config)
    _validate_writing_preamble(normalized_config)
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
        normalized_config=normalized_config,
        partner_distributions=partner_distribution_index,
    )
