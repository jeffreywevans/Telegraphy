from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

from ._constants import PARTNER_DISTRIBUTIONS_KEY
from .availability_validation import has_date_overlap
from .partner_models import (
    PartnerDistributionDataset,
    parse_partner_distribution_payload,
)
from .schema_validation_common import (
    validate_no_duplicate_strings,
    validate_string_list,
)

CONFIG_REQUIRED_KEYS = frozenset({
    "schema_version",
    "dataset_version",
    "date_start",
    "date_end",
    "sexual_content_presence_options",
    "sexual_content_presence_weights",
    "sexual_scene_tag_groups",
    "sexual_scene_tag_count_weights_by_presence",
    "sexual_scene_required_tag_groups_by_presence",
    "sexual_scene_optional_tag_groups",
    "word_count_targets",
    "ordered_keys",
    "writing_preamble",
})

EXPECTED_GENERATED_FIELD_KEYS = frozenset({
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
})
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


def validate_config_versions(config: dict[str, Any]) -> None:
    if not isinstance(config["schema_version"], int) or config["schema_version"] < 1:
        raise ValueError("config.schema_version must be an integer >= 1")
    if not isinstance(config["dataset_version"], str) or not config["dataset_version"].strip():
        raise ValueError("config.dataset_version must be a non-empty string")


def parse_and_validate_config_dates(config: dict[str, Any]) -> tuple[date, date]:
    try:
        start = date.fromisoformat(str(config["date_start"]))
        end = date.fromisoformat(str(config["date_end"]))
    except ValueError as exc:
        raise ValueError("config date_start/date_end must be ISO dates (YYYY-MM-DD)") from exc
    if start > end:
        raise ValueError("config.date_start must be <= config.date_end")
    return start, end


def validate_config_date_overlap(
    character_rows: list[tuple[str, date, date]],
    setting_rows: list[tuple[str, date, date]],
    start: date,
    end: date,
    character_key: str,
    setting_key: str,
) -> None:
    if not has_date_overlap(character_rows, start, end):
        raise ValueError(f"config date range has no overlap with entities.{character_key}")
    if not has_date_overlap(setting_rows, start, end):
        raise ValueError(f"config date range has no overlap with entities.{setting_key}")


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


def validate_sexual_content_weights(config: dict[str, Any]) -> None:
    validate_string_list(
        "config", "sexual_content_presence_options", config["sexual_content_presence_options"]
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


def validate_word_count_targets(config: dict[str, Any]) -> None:
    targets = config["word_count_targets"]
    if not isinstance(targets, list) or not targets:
        raise ValueError("config.word_count_targets must be a non-empty list")
    for idx, value in enumerate(targets):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"config.word_count_targets[{idx}] must be a positive integer")


def validate_sexual_scene_tag_groups(config: dict[str, Any]) -> None:
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
        validate_string_list("config", f"sexual_scene_tag_groups.{group_name}", tags)
        validate_no_duplicate_strings("config", f"sexual_scene_tag_groups.{group_name}", tags)


_NON_NEGATIVE_INT_PATTERN = re.compile(r"0|[1-9]\d*")


def _parse_non_negative_weight_count(raw_count: Any, field_name: str, min_count: int = 0) -> int:
    minimum_label = "positive" if min_count > 0 else "non-negative"
    error_message = f"{field_name} must be {minimum_label} integers, got {raw_count!r}"

    if isinstance(raw_count, bool):
        raise ValueError(error_message)

    if isinstance(raw_count, str) and _NON_NEGATIVE_INT_PATTERN.fullmatch(raw_count):
        count = int(raw_count)
    elif isinstance(raw_count, int):
        count = raw_count
    else:
        raise ValueError(error_message)

    if count < min_count:
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


def validate_sexual_scene_tag_count_weights_by_presence(config: dict[str, Any]) -> None:
    raw_by_presence = config["sexual_scene_tag_count_weights_by_presence"]
    if not isinstance(raw_by_presence, dict) or not raw_by_presence:
        raise ValueError(
            "config.sexual_scene_tag_count_weights_by_presence must be a non-empty object"
        )

    group_count = len(config["sexual_scene_tag_groups"])
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
                min_count=0,
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


def validate_sexual_scene_tag_group_presence_rules(config: dict[str, Any]) -> None:
    group_names = set(config["sexual_scene_tag_groups"])
    required_by_presence = config["sexual_scene_required_tag_groups_by_presence"]
    optional_groups = config["sexual_scene_optional_tag_groups"]

    if not isinstance(required_by_presence, dict):
        raise ValueError("config.sexual_scene_required_tag_groups_by_presence must be an object")
    if not isinstance(optional_groups, list):
        raise ValueError("config.sexual_scene_optional_tag_groups must be a list")
    if optional_groups:
        validate_string_list("config", "sexual_scene_optional_tag_groups", optional_groups)
        validate_no_duplicate_strings("config", "sexual_scene_optional_tag_groups", optional_groups)

    _raise_for_unknown_optional_groups(optional_groups, group_names)
    _raise_for_unknown_presence_options(
        required_by_presence,
        config["sexual_content_presence_options"],
    )

    for presence, groups in required_by_presence.items():
        _validate_required_groups_for_presence(
            presence=presence,
            groups=groups,
            group_names=group_names,
            tag_count_weights_by_presence=config["sexual_scene_tag_count_weights_by_presence"],
        )

    _raise_for_missing_required_presence_options(
        required_by_presence,
        config["sexual_scene_tag_count_weights_by_presence"],
    )


def _raise_for_unknown_optional_groups(optional_groups: list[str], group_names: set[str]) -> None:
    unknown_optional = sorted(group for group in optional_groups if group not in group_names)
    if unknown_optional:
        raise ValueError(
            "config.sexual_scene_optional_tag_groups contains unknown groups: "
            + ", ".join(unknown_optional)
        )


def _raise_for_unknown_presence_options(
    required_by_presence: dict[str, Any],
    presence_options: list[str],
) -> None:
    valid_presence_options = set(presence_options)
    unknown_presence = sorted(
        presence for presence in required_by_presence if presence not in valid_presence_options
    )
    if unknown_presence:
        raise ValueError(
            "config.sexual_scene_required_tag_groups_by_presence contains unknown presence "
            f"options: {', '.join(unknown_presence)}"
        )


def _validate_required_groups_for_presence(
    *,
    presence: str,
    groups: Any,
    group_names: set[str],
    tag_count_weights_by_presence: dict[str, dict[Any, float]],
) -> None:
    if not isinstance(groups, list):
        raise ValueError(
            "config.sexual_scene_required_tag_groups_by_presence."
            f"{presence} must be a list"
        )

    if groups:
        field_name = f"sexual_scene_required_tag_groups_by_presence.{presence}"
        validate_string_list("config", field_name, groups)
        validate_no_duplicate_strings("config", field_name, groups)

    _raise_for_unknown_required_groups(presence, groups, group_names)
    _raise_for_excess_required_groups(presence, groups, tag_count_weights_by_presence)


def _get_min_allowed_tag_count(tag_count_weights: dict[Any, float]) -> int:
    allowed_tag_counts = [int(count) for count, weight in tag_count_weights.items() if weight > 0]
    return min(allowed_tag_counts, default=0)


def _raise_for_excess_required_groups(
    presence: str,
    groups: list[str],
    tag_count_weights_by_presence: dict[str, dict[Any, float]],
) -> None:
    if presence != "none":
        return

    tag_count_weights = tag_count_weights_by_presence[presence]
    min_allowed = _get_min_allowed_tag_count(tag_count_weights)
    if len(groups) > min_allowed:
        group_count = len(groups)
        raise ValueError(
            f"config.sexual_scene_required_tag_groups_by_presence.{presence} "
            f"requires {group_count} group{'s' if group_count != 1 else ''}, but "
            f"config.sexual_scene_tag_count_weights_by_presence.{presence} "
            f"allows as few as {min_allowed} tag{'s' if min_allowed != 1 else ''}"
        )


def _raise_for_unknown_required_groups(
    presence: str,
    groups: list[str],
    group_names: set[str],
) -> None:
    unknown_required = sorted(group for group in groups if group not in group_names)
    if unknown_required:
        raise ValueError(
            "config.sexual_scene_required_tag_groups_by_presence."
            f"{presence} contains unknown groups: {', '.join(unknown_required)}"
        )


def _raise_for_missing_required_presence_options(
    required_by_presence: dict[str, Any],
    tag_count_weights_by_presence: dict[str, dict[Any, float]],
) -> None:
    required_presence_options = set(tag_count_weights_by_presence)
    missing_presence = sorted(required_presence_options - set(required_by_presence))
    if not missing_presence:
        return

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


def validate_ordered_keys(config: dict[str, Any]) -> None:
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


def validate_writing_preamble(config: dict[str, Any]) -> None:
    if not isinstance(config["writing_preamble"], str) or not config["writing_preamble"].strip():
        raise ValueError("config.writing_preamble must be a non-empty string")


def validate_partner_distributions(
    partner_payload: dict[str, Any],
    *,
    config_start: date,
    config_end: date,
    character_rows: list[tuple[str, date, date]],
) -> PartnerDistributionDataset:
    return parse_partner_distribution_payload(
        partner_payload,
        config_start=config_start,
        config_end=config_end,
        character_rows=character_rows,
        partner_distributions_key=PARTNER_DISTRIBUTIONS_KEY,
    )


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(config)

    present_unsupported_aliases = [
        key for key in UNSUPPORTED_CONFIG_ALIAS_KEYS if key in normalized
    ]
    if present_unsupported_aliases:
        joined = ", ".join(sorted(present_unsupported_aliases))
        raise ValueError(f"{UNSUPPORTED_CONFIG_ALIAS_ERROR_PREFIX}{joined}")

    normalized.setdefault("sexual_scene_optional_tag_groups", [])
    return normalized
