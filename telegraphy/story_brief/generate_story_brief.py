#!/usr/bin/env python3
"""Generate a random story brief as Markdown with YAML front matter."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import secrets
from copy import deepcopy
from datetime import date, datetime, timedelta
from functools import lru_cache
from importlib.resources import files
from pathlib import Path, PurePath
from typing import Any, Iterable, NamedTuple, Sequence, TypedDict, TypeVar

import yaml

if __package__ in (None, ""):
    from partner_models import parse_partner_distribution_payload, require_keys
else:
    from .partner_models import parse_partner_distribution_payload, require_keys

PoolValue = TypeVar("PoolValue", str, int)

TITLE_TOKEN_PATTERN = re.compile(r"@(?P<key>protagonist|setting|time_period)\b")
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
SEXUAL_SCENE_TAG_COUNT_OPTIONS = (2, 3, 4, 5)
SEXUAL_SCENE_TAG_COUNT_WEIGHTS = (0.7, 0.1, 0.1, 0.1)
MAX_SEXUAL_SCENE_TAG_GROUPS = 10
if len(SEXUAL_SCENE_TAG_COUNT_OPTIONS) != len(SEXUAL_SCENE_TAG_COUNT_WEIGHTS):
    raise ValueError(
        "SEXUAL_SCENE_TAG_COUNT_OPTIONS and SEXUAL_SCENE_TAG_COUNT_WEIGHTS "
        "must have matching lengths"
    )
if len(set(SEXUAL_SCENE_TAG_COUNT_OPTIONS)) != len(SEXUAL_SCENE_TAG_COUNT_OPTIONS):
    raise ValueError("SEXUAL_SCENE_TAG_COUNT_OPTIONS must not contain duplicates")
SEXUAL_SCENE_TAG_COUNT_WEIGHT_BY_OPTION = dict(
    zip(SEXUAL_SCENE_TAG_COUNT_OPTIONS, SEXUAL_SCENE_TAG_COUNT_WEIGHTS)
)
PROMPT_LIST_KEYS = (
    "central_conflicts",
    "inciting_pressures",
    "ending_types",
    "style_guidance",
    "weather",
)
PROMPT_LIST_KEYS_SET = frozenset(PROMPT_LIST_KEYS)
CHARACTER_AVAILABILITY_KEY = "character_availability"
SETTING_AVAILABILITY_KEY = "setting_availability"
PARTNER_DISTRIBUTIONS_KEY = "partner_distributions"
TITLES_FILENAME = "titles.json"
ENTITIES_FILENAME = "entities.json"
PROMPTS_FILENAME = "prompts.json"
CONFIG_FILENAME = "config.json"
PARTNER_DISTRIBUTIONS_FILENAME = "partner_distributions.json"
STORY_DATASET_FILES = {
    "titles": TITLES_FILENAME,
    "entities": ENTITIES_FILENAME,
    "prompts": PROMPTS_FILENAME,
    "config": CONFIG_FILENAME,
    "partner_distributions": PARTNER_DISTRIBUTIONS_FILENAME,
}
ENTITY_AVAILABILITY_KEYS = frozenset(
    {
        CHARACTER_AVAILABILITY_KEY,
        SETTING_AVAILABILITY_KEY,
    }
)
WINDOWS_RESERVED_BASENAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


class ValidatedStoryData(NamedTuple):
    character_availability: list[tuple[str, date, date]]
    setting_availability: list[tuple[str, date, date]]
    date_start: date
    date_end: date
    partner_distributions: dict[str, list[dict[str, Any]]]


class DatasetLintReport(NamedTuple):
    errors: list[str]
    warnings: list[str]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


class StoryData(TypedDict):
    titles: tuple[str, ...]
    titles_sorted: tuple[str, ...]
    character_availability: tuple[tuple[str, date, date], ...]
    setting_availability: tuple[tuple[str, date, date], ...]
    central_conflicts: tuple[str, ...]
    inciting_pressures: tuple[str, ...]
    ending_types: tuple[str, ...]
    style_guidance: tuple[str, ...]
    weather: tuple[str, ...]
    central_conflicts_sorted: tuple[str, ...]
    inciting_pressures_sorted: tuple[str, ...]
    ending_types_sorted: tuple[str, ...]
    style_guidance_sorted: tuple[str, ...]
    weather_sorted: tuple[str, ...]
    date_start: date
    date_end: date
    sexual_content_options: tuple[str, ...]
    sexual_content_weights: tuple[float, ...]
    sexual_scene_tag_groups: dict[str, tuple[str, ...]]
    sexual_scene_tag_group_names_sorted: tuple[str, ...]
    sexual_scene_tag_groups_sorted: dict[str, tuple[str, ...]]
    word_count_targets: tuple[int, ...]
    word_count_targets_sorted: tuple[int, ...]
    ordered_keys: tuple[str, ...]
    writing_preamble: str
    dataset_version: str
    partner_distributions: dict[str, tuple[dict[str, Any], ...]]


def _load_json(path: Any) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _data_file(filename: str) -> Any:
    """
    Resolve a story-brief data file.

    Resolution order:
      1) TELEGRAPHY_DATA_DIR env var (custom/system deployments).
         Falls back to COMMUTED_STORY_BRIEF_DATA_DIR for backwards compatibility.
      2) Direct-script source checkout fallback (repo-relative `data/`).
      3) Installed package resources under
         telegraphy.story_brief.data (packaged installs).

    Why this chain exists:
      - Allows testing against alternate datasets without code changes.
      - Supports container/ops setups that mount data at runtime.
      - Keeps editable local data working during development.
    """
    override_raw = os.environ.get("TELEGRAPHY_DATA_DIR") or os.environ.get(
        "COMMUTED_STORY_BRIEF_DATA_DIR"
    )
    if override_raw:
        return _resolve_data_dir_override(override_raw) / filename

    repo_relative = Path(__file__).resolve().parent / "data" / filename
    if __package__ in (None, "") and repo_relative.exists():
        return repo_relative

    try:
        return files("telegraphy.story_brief.data").joinpath(filename)
    except (ModuleNotFoundError, FileNotFoundError):
        return repo_relative


def _resolve_data_dir_override(path_raw: str) -> Path:
    """Resolve and validate TELEGRAPHY_DATA_DIR style overrides."""
    trimmed = path_raw.strip()
    if not trimmed:
        raise ValueError("Configured data directory must not be empty")
    if "\x00" in trimmed:
        raise ValueError("Configured data directory must not contain NUL bytes")

    raw_path = Path(trimmed).expanduser()
    if not raw_path.is_absolute():
        raise ValueError("Configured data directory must be an absolute path")

    candidate = raw_path.resolve(strict=True)
    if not candidate.is_dir():
        raise ValueError(
            "Configured data directory must be an existing directory: "
            f"{candidate}"
        )

    return candidate


def _write_output_markdown(output_path: Path, markdown: str, *, force: bool) -> None:
    """
    Write markdown to output_path while guarding against symlink redirection.

    Uses low-level os.open flags so writes fail closed for symlink targets and
    so non-force writes are performed with O_EXCL.
    """
    trusted_base_dir = Path.cwd().resolve(strict=True)
    raw_output_path = trusted_base_dir / output_path
    resolved_parent = raw_output_path.parent.resolve(strict=False)
    candidate_output_path = resolved_parent / raw_output_path.name
    if not resolved_parent.is_relative_to(trusted_base_dir):
        raise SystemExit("Resolved output path must be within the trusted base directory.")

    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_TRUNC if force else os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    mode = 0o600

    try:
        fd = os.open(candidate_output_path, flags, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(markdown)
    except FileExistsError:
        raise SystemExit(
            "Refusing to overwrite existing file. Use --force to overwrite."
        ) from None
    except OSError as exc:
        raise SystemExit(
            f"Unable to safely open or write output path ({exc.strerror})"
        ) from None


def _build_safe_relative_path(path_raw: str, *, trusted_base_dir: Path) -> Path:
    """
    Build a relative path from untrusted text by rejecting traversal segments.

    This intentionally allows nested directories but blocks absolute paths, home
    shortcuts, and parent-directory traversal.
    """
    trimmed = path_raw.strip()
    if not trimmed:
        return Path(".")
    if trimmed.startswith("~"):
        raise ValueError("path must not begin with '~'")

    candidate = trimmed
    if os.path.isabs(trimmed):
        normalized_base = os.path.normcase(os.path.realpath(str(trusted_base_dir)))
        normalized_candidate = os.path.normcase(os.path.realpath(trimmed))
        try:
            common_root = os.path.commonpath([normalized_base, normalized_candidate])
        except ValueError as exc:
            raise ValueError(
                f"absolute paths must remain inside the base directory: {normalized_base!r}"
            ) from exc
        if common_root != normalized_base:
            raise ValueError(
                f"absolute paths must remain inside the base directory: {normalized_base!r}"
            )
        candidate = os.path.relpath(normalized_candidate, normalized_base)

    raw_parts = [part for part in re.split(r"[\\/]+", candidate) if part and part != "."]
    if any(part == ".." for part in raw_parts):
        raise ValueError("path must not include parent-directory traversal ('..')")
    return Path(*raw_parts) if raw_parts else Path(".")


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


def _parse_availability_boundary(value: Any) -> date:
    if isinstance(value, bool):
        raise ValueError("boundary values must not be booleans")
    if isinstance(value, int):
        return date(value, 1, 1)
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("boundary string values must be ISO dates (YYYY-MM-DD)") from exc
    raise ValueError("boundary values must be an integer year or ISO date string")


def _validate_availability_rows(
    section_name: str, key: str, rows: Any
) -> list[tuple[str, date, date]]:
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{section_name}.{key} must be a non-empty list")
    parsed_rows: list[tuple[str, date, date]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError(f"{section_name}.{key}[{idx}] must be [name, start, end]")
        name, start_boundary, end_boundary = row
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{section_name}.{key}[{idx}][0] must be a non-empty string")
        name = name.strip()
        try:
            start = _parse_availability_boundary(start_boundary)
            end = _parse_availability_boundary(end_boundary)
        except ValueError as exc:
            raise ValueError(f"{section_name}.{key}[{idx}] {exc}") from exc
        if start > end:
            raise ValueError(
                f"{section_name}.{key}[{idx}] start must be <= end"
            )
        parsed_rows.append((name, start, end))

    _validate_availability_name_windows(section_name, key, parsed_rows)
    return parsed_rows


def _validate_availability_name_windows(
    section_name: str, key: str, rows: list[tuple[str, date, date]]
) -> None:
    windows_by_name: dict[str, list[tuple[date, date, int]]] = {}
    for idx, row in enumerate(rows):
        name, start, end = row
        name_norm = name.casefold()
        windows_by_name.setdefault(name_norm, []).append((start, end, idx))

    for name_windows in windows_by_name.values():
        name_windows.sort(key=lambda item: item[0])
        for prev, curr in zip(name_windows, name_windows[1:]):
            _, prev_end, prev_idx = prev
            curr_start, _, curr_idx = curr
            if curr_start <= prev_end:
                raise ValueError(
                    f"{section_name}.{key} has overlapping availability windows "
                    f"for the same name at indices {prev_idx} and {curr_idx}"
                )


def _has_date_overlap(
    rows: list[tuple[str, date, date]], range_start: date, range_end: date
) -> bool:
    for _, start, end in rows:
        if start <= range_end and end >= range_start:
            return True
    return False


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
    character_rows = _validate_availability_rows(
        "entities", CHARACTER_AVAILABILITY_KEY, entities[CHARACTER_AVAILABILITY_KEY]
    )
    setting_rows = _validate_availability_rows(
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
    if not _has_date_overlap(character_rows, start, end):
        raise ValueError(
            f"config date range has no overlap with entities.{CHARACTER_AVAILABILITY_KEY}"
        )
    if not _has_date_overlap(setting_rows, start, end):
        raise ValueError(
            f"config date range has no overlap with entities.{SETTING_AVAILABILITY_KEY}"
        )


def _validate_sexual_content_weights(config: dict[str, Any]) -> None:
    _validate_string_list(
        "config", "sexual_content_options", config["sexual_content_options"]
    )
    weights = config["sexual_content_weights"]
    if not isinstance(weights, list) or not weights:
        raise ValueError("config.sexual_content_weights must be a non-empty list")
    if len(weights) != len(config["sexual_content_options"]):
        raise ValueError("config sexual_content_options/weights must be the same length")
    for idx, value in enumerate(weights):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"config.sexual_content_weights[{idx}] must be a real number"
            )
        if not math.isfinite(value):
            raise ValueError(
                f"config.sexual_content_weights[{idx}] must be finite"
            )
        if value < 0:
            raise ValueError(
                f"config.sexual_content_weights[{idx}] must be non-negative"
            )
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
        _validate_no_duplicate_strings(
            "config", f"sexual_scene_tag_groups.{group_name}", tags
        )


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
) -> dict[str, list[dict[str, Any]]]:
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


def load_story_data() -> StoryData:
    """Load, validate, and normalize the story dataset used by the generator."""
    try:
        dataset_payloads = {
            key: _load_json(_data_file(filename))
            for key, filename in STORY_DATASET_FILES.items()
        }
    except FileNotFoundError as exc:
        missing_name = Path(exc.filename).name if exc.filename else "unknown file"
        location = (
            "configured data directory (TELEGRAPHY_DATA_DIR or COMMUTED_STORY_BRIEF_DATA_DIR)"
            if os.environ.get("TELEGRAPHY_DATA_DIR")
            or os.environ.get("COMMUTED_STORY_BRIEF_DATA_DIR")
            else "data directory"
        )
        raise ValueError(
            f"Failed to load story brief dataset file '{missing_name}' from {location}. "
            "Verify the directory exists and contains the required JSON files."
        ) from exc
    titles = dataset_payloads["titles"]
    entities = dataset_payloads["entities"]
    prompts = dataset_payloads["prompts"]
    config = dataset_payloads["config"]
    partner_distributions = dataset_payloads["partner_distributions"]
    validated = validate_story_data(titles, entities, prompts, config, partner_distributions)
    prompt_lists = {key: tuple(str(value) for value in prompts[key]) for key in PROMPT_LIST_KEYS}

    sexual_scene_tag_groups = {
        str(group_name): tuple(str(tag) for tag in tags)
        for group_name, tags in config["sexual_scene_tag_groups"].items()
    }

    return {
        "titles": tuple(str(v) for v in titles["titles"]),
        "titles_sorted": tuple(stable_sorted_pool(str(v) for v in titles["titles"])),
        CHARACTER_AVAILABILITY_KEY: tuple(validated.character_availability),
        SETTING_AVAILABILITY_KEY: tuple(validated.setting_availability),
        **prompt_lists,
        **{
            f"{key}_sorted": tuple(stable_sorted_pool(prompt_lists[key]))
            for key in PROMPT_LIST_KEYS
        },
        "date_start": validated.date_start,
        "date_end": validated.date_end,
        "sexual_content_options": tuple(str(v) for v in config["sexual_content_options"]),
        "sexual_content_weights": tuple(float(v) for v in config["sexual_content_weights"]),
        "sexual_scene_tag_groups": sexual_scene_tag_groups,
        "sexual_scene_tag_group_names_sorted": tuple(stable_sorted_pool(sexual_scene_tag_groups)),
        "sexual_scene_tag_groups_sorted": {
            group_name: tuple(stable_sorted_pool(tags))
            for group_name, tags in sexual_scene_tag_groups.items()
        },
        "word_count_targets": tuple(int(v) for v in config["word_count_targets"]),
        "word_count_targets_sorted": tuple(
            stable_sorted_pool(int(v) for v in config["word_count_targets"])
        ),
        "ordered_keys": tuple(str(v) for v in config["ordered_keys"]),
        "writing_preamble": str(config["writing_preamble"]),
        "dataset_version": str(config["dataset_version"]),
        PARTNER_DISTRIBUTIONS_KEY: {
            protagonist: tuple(
                {**era, "partners": tuple(era["partners"])}
                for era in eras
            )
            for protagonist, eras in validated.partner_distributions.items()
        },
    }


@lru_cache(maxsize=1)
def _get_data_cached() -> StoryData:
    """Load and cache story-brief data on first use."""
    return load_story_data()


def _clear_get_data_cache() -> None:
    _get_data_cached.cache_clear()


def clear_get_data_cache() -> None:
    """Clear the memoized story dataset cache."""
    _clear_get_data_cache()


def get_data() -> StoryData:
    """Load and cache story-brief data on first use.

    Returns a deep copy of cached data to prevent cache poisoning when callers
    mutate nested structures.
    """
    return deepcopy(_get_data_cached())


_COMPAT_ALIASES: dict[str, str] = {
    "TITLES": "titles",
    "PROTAGONIST_AVAILABILITY": CHARACTER_AVAILABILITY_KEY,
    "CHARACTER_AVAILABILITY": CHARACTER_AVAILABILITY_KEY,
    "SETTING_AVAILABILITY": SETTING_AVAILABILITY_KEY,
    "CENTRAL_CONFLICTS": "central_conflicts",
    "INCITING_PRESSURES": "inciting_pressures",
    "ENDING_TYPES": "ending_types",
    "STYLE_GUIDANCE": "style_guidance",
    "WEATHER": "weather",
    "DATE_START": "date_start",
    "DATE_END": "date_end",
    "SEXUAL_CONTENT_OPTIONS": "sexual_content_options",
    "SEXUAL_CONTENT_WEIGHTS": "sexual_content_weights",
    "SEXUAL_SCENE_TAG_GROUPS": "sexual_scene_tag_groups",
    "WORD_COUNT_TARGETS": "word_count_targets",
    "ORDERED_KEYS": "ordered_keys",
    "WRITING_PREAMBLE": "writing_preamble",
    "DATASET_VERSION": "dataset_version",
    "PARTNER_DISTRIBUTIONS": PARTNER_DISTRIBUTIONS_KEY,
}


def __getattr__(name: str) -> Any:
    """Compatibility layer for legacy module-level constants."""
    if name in _COMPAT_ALIASES:
        return deepcopy(_get_data_cached()[_COMPAT_ALIASES[name]])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


MAX_FILENAME_STEM_LENGTH = 120
MAX_FILENAME_TOTAL_BYTES = 255
SAFE_FILENAME_INPUT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,254}$")


def _validate_user_filename_input(filename: str) -> None:
    """
    Validate raw user-provided filename before sanitization.

    Allows a conservative character set and rejects path semantics.
    """
    if not filename or filename.strip() != filename:
        raise ValueError("filename must be non-empty and must not have leading/trailing spaces")
    if "/" in filename or "\\" in filename:
        raise ValueError("filename must not contain path separators")
    if filename in {".", ".."} or ".." in filename:
        raise ValueError("filename must not contain dot-segments")
    if not SAFE_FILENAME_INPUT_PATTERN.fullmatch(filename):
        raise ValueError(
            "filename must be 1-255 characters, start with a letter or number, "
            "and contain only letters, numbers, space, dot, underscore, or hyphen"
        )


def _truncate_utf8(value: str, max_bytes: int) -> str:
    """Return value truncated to max_bytes when UTF-8 encoded."""
    if max_bytes <= 0:
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", "ignore")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for cross-platform safety while preserving extension.

    Removes control chars and characters invalid on Windows/macOS/Linux,
    strips trailing dots/spaces, and avoids reserved Windows base names.
    """
    name = PurePath(filename).name
    stem, suffix = os.path.splitext(name)

    # Remove control chars and characters invalid on common filesystems.
    safe_stem = re.sub(r'[\x00-\x1f<>:"/\\|?*]+', "-", stem).rstrip(" .-")
    safe_stem = safe_stem[:MAX_FILENAME_STEM_LENGTH].rstrip(" .-")
    safe_suffix = re.sub(r'[\x00-\x1f<>:"/\\|?*]+', "", suffix).rstrip(" .")

    if not safe_stem:
        safe_stem = "story-brief"

    if safe_stem.casefold() in WINDOWS_RESERVED_BASENAMES:
        safe_stem = f"{safe_stem}-file"

    if safe_suffix and not safe_suffix.startswith("."):
        safe_suffix = f".{safe_suffix}"

    safe_suffix = _truncate_utf8(safe_suffix, MAX_FILENAME_TOTAL_BYTES - 1).rstrip(" .")
    if safe_suffix == ".":
        safe_suffix = ""

    max_stem_bytes = MAX_FILENAME_TOTAL_BYTES - len(safe_suffix.encode("utf-8"))
    safe_stem = _truncate_utf8(safe_stem, max_stem_bytes).rstrip(" .-")
    if not safe_stem:
        safe_stem = _truncate_utf8("story-brief", max_stem_bytes).rstrip(" .-") or "s"

    if safe_stem.casefold() in WINDOWS_RESERVED_BASENAMES:
        safe_stem = _truncate_utf8(f"{safe_stem}-file", max_stem_bytes).rstrip(" .-")
        if safe_stem.casefold() in WINDOWS_RESERVED_BASENAMES:
            safe_stem = _truncate_utf8("file", max_stem_bytes) or "f"

    return f"{safe_stem}{safe_suffix}"


def build_auto_filename(title: str, today: date | datetime | str | None = None) -> str:
    """Build a sanitized default filename with a non-empty slug fallback."""
    slug = slugify(title) or "story-brief"
    if isinstance(today, str):
        date_prefix = today
    else:
        date_prefix = (today or datetime.now()).strftime("%Y-%m-%d")
    return sanitize_filename(f"{date_prefix} {slug}.md")


def escape_markdown_heading_text(value: str) -> str:
    """Escape Markdown-significant characters for safe heading rendering."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!])", r"\\\1", value)


def random_date_in_range(
    rng: random.Random | secrets.SystemRandom, start: date, end: date
) -> date:
    """Return a random date between start and end (inclusive)."""
    day_span = (end - start).days
    return start + timedelta(days=rng.randint(0, day_span))


def available_characters(
    selected_date: date, data: dict[str, Any] | None = None
) -> list[str]:
    """Return characters available for the selected date."""
    resolved_data = get_data() if data is None else data
    return [
        name
        for name, start_date, end_date in resolved_data[CHARACTER_AVAILABILITY_KEY]
        if start_date <= selected_date <= end_date
    ]


def stable_sorted_pool(values: Iterable[PoolValue]) -> list[PoolValue]:
    """Return a consistently sorted copy for seed-stable random selection."""
    return sorted(values)


def sorted_pool_from_data(data: dict[str, Any], key: str) -> Sequence[PoolValue]:
    """Read a pre-sorted pool from data when present, else sort lazily."""
    sorted_key = f"{key}_sorted"
    if sorted_key in data:
        return data[sorted_key]
    return stable_sorted_pool(data[key])


def available_settings(
    selected_date: date, data: dict[str, Any] | None = None
) -> list[str]:
    """Return settings available for the selected date."""
    resolved_data = get_data() if data is None else data
    return [
        setting
        for setting, start_date, end_date in resolved_data[SETTING_AVAILABILITY_KEY]
        if start_date <= selected_date <= end_date
    ]


def weighted_choice(
    rng: random.Random | secrets.SystemRandom,
    options: Sequence[str],
    weights: Sequence[float],
) -> str:
    """Pick one option using relative weights."""
    if not options:
        raise ValueError("options must not be empty")
    if not weights:
        raise ValueError("weights must not be empty")
    if len(options) != len(weights):
        raise ValueError("options and weights must be the same length")

    for index, weight in enumerate(weights):
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise TypeError(f"weight at index {index} must be a real number")
        if not math.isfinite(weight):
            raise ValueError(f"weight at index {index} must be finite")
        if weight < 0:
            raise ValueError(f"weight at index {index} must be non-negative")

    total = sum(weights)
    if total <= 0:
        raise ValueError("at least one weight must be greater than zero")

    threshold = rng.random() * total
    cumulative = 0.0

    for option, weight in zip(options, weights):
        cumulative += weight
        if threshold < cumulative:
            return option

    return options[-1]


@lru_cache(maxsize=16)
def symmetric_peak_weights(length: int) -> tuple[float, ...]:
    """Build symmetric bell-curve-like weights with a center peak."""
    if length <= 0:
        raise ValueError("length must be greater than zero")
    return tuple(float(min(index, length - 1 - index) + 1) for index in range(length))


def render_title(
    template: str, *, protagonist: str, setting: str, time_period: str
) -> str:
    """Render @token placeholders in title templates."""
    values = {
        "protagonist": protagonist,
        "setting": setting,
        "time_period": time_period,
    }
    return TITLE_TOKEN_PATTERN.sub(lambda match: values[match.group("key")], template)


def _add_clipped_range_checkpoints(
    *,
    checkpoints: set[date],
    ranges: Iterable[tuple[date, date]],
    range_start: date,
    range_end: date,
) -> None:
    one_day = timedelta(days=1)
    for row_start, row_end in ranges:
        clipped_start = max(range_start, row_start)
        clipped_end = min(range_end, row_end)
        if clipped_start <= clipped_end:
            checkpoints.add(clipped_start)
            if clipped_end < range_end:
                checkpoints.add(clipped_end + one_day)


def validate_story_data_strict(data: dict[str, Any]) -> None:
    """Validate per-date generation preconditions across the configured date range."""
    range_start = data["date_start"]
    range_end = data["date_end"]
    checkpoints: set[date] = {range_start, range_end}
    for source in (data[CHARACTER_AVAILABILITY_KEY], data[SETTING_AVAILABILITY_KEY]):
        _add_clipped_range_checkpoints(
            checkpoints=checkpoints,
            ranges=((row_start, row_end) for _, row_start, row_end in source),
            range_start=range_start,
            range_end=range_end,
        )
    for selected_date in sorted(checkpoints):
        characters = [
            name
            for name, start_date, end_date_for_row in data[CHARACTER_AVAILABILITY_KEY]
            if start_date <= selected_date <= end_date_for_row
        ]
        if len(characters) < 2:
            raise ValueError(
                "Strict validation failed: fewer than two distinct available characters on "
                f"{selected_date.isoformat()}."
            )

        if not any(
            start_date <= selected_date <= end_date_for_row
            for _, start_date, end_date_for_row in data[SETTING_AVAILABILITY_KEY]
        ):
            raise ValueError(
                "Strict validation failed: no available settings on "
                f"{selected_date.isoformat()}."
            )


def _format_date_ranges(ranges: list[tuple[date, date]]) -> str:
    if not ranges:
        return "none"
    rendered = []
    for start, end in ranges:
        if start == end:
            rendered.append(start.isoformat())
        else:
            rendered.append(f"{start.isoformat()}..{end.isoformat()}")
    return ", ".join(rendered)


def _coalesce_ranges(ranges: list[tuple[date, date]]) -> list[tuple[date, date]]:
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda item: item[0])
    merged: list[tuple[date, date]] = [sorted_ranges[0]]
    one_day = timedelta(days=1)
    for current_start, current_end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        if current_start <= last_end + one_day:
            merged[-1] = (last_start, max(last_end, current_end))
            continue
        merged.append((current_start, current_end))
    return merged


def _build_lint_checkpoints(
    data: dict[str, Any], *, range_start: date, range_end: date
) -> list[date]:
    one_day = timedelta(days=1)
    checkpoints: set[date] = {range_start}
    checkpoints.add(range_end + one_day if range_end < date.max else range_end)

    for source in (data[CHARACTER_AVAILABILITY_KEY], data[SETTING_AVAILABILITY_KEY]):
        _add_clipped_range_checkpoints(
            checkpoints=checkpoints,
            ranges=((row_start, row_end) for _, row_start, row_end in source),
            range_start=range_start,
            range_end=range_end,
        )
    for eras in data[PARTNER_DISTRIBUTIONS_KEY].values():
        _add_clipped_range_checkpoints(
            checkpoints=checkpoints,
            ranges=((era["date_start"], era["date_end"]) for era in eras),
            range_start=range_start,
            range_end=range_end,
        )

    return sorted(checkpoints)


def _available_entities(
    availability_rows: Sequence[tuple[str, date, date]], *, selected_date: date
) -> list[str]:
    return [
        name
        for name, start_date, end_date in availability_rows
        if start_date <= selected_date <= end_date
    ]


def _collect_interval_lint_ranges(
    data: dict[str, Any], *, sorted_checkpoints: Sequence[date], range_end: date
) -> tuple[
    list[tuple[date, date]],
    list[tuple[date, date]],
    list[tuple[date, date]],
    list[tuple[date, date]],
    dict[str, list[tuple[date, date]]],
]:
    one_day = timedelta(days=1)
    missing_character_ranges: list[tuple[date, date]] = []
    thin_character_ranges: list[tuple[date, date]] = []
    missing_setting_ranges: list[tuple[date, date]] = []
    thin_setting_ranges: list[tuple[date, date]] = []
    partner_data_gap_ranges_by_protagonist: dict[str, list[tuple[date, date]]] = {}

    for current_start, next_start in zip(sorted_checkpoints, sorted_checkpoints[1:]):
        interval_end = min(range_end, next_start - one_day)
        if interval_end < current_start:
            continue

        characters = _available_entities(
            data[CHARACTER_AVAILABILITY_KEY], selected_date=current_start
        )
        settings = _available_entities(
            data[SETTING_AVAILABILITY_KEY], selected_date=current_start
        )

        if len(characters) < 2:
            missing_character_ranges.append((current_start, interval_end))
        elif len(characters) == 2:
            thin_character_ranges.append((current_start, interval_end))

        if not settings:
            missing_setting_ranges.append((current_start, interval_end))
        elif len(settings) == 1:
            thin_setting_ranges.append((current_start, interval_end))

        for protagonist in characters:
            eras = data[PARTNER_DISTRIBUTIONS_KEY].get(protagonist, [])
            if any(era["date_start"] <= current_start <= era["date_end"] for era in eras):
                continue
            partner_data_gap_ranges_by_protagonist.setdefault(protagonist, []).append(
                (current_start, interval_end)
            )

    return (
        missing_character_ranges,
        thin_character_ranges,
        missing_setting_ranges,
        thin_setting_ranges,
        partner_data_gap_ranges_by_protagonist,
    )


def _append_coverage_messages(
    *,
    errors: list[str],
    warnings: list[str],
    missing_character_ranges: list[tuple[date, date]],
    thin_character_ranges: list[tuple[date, date]],
    missing_setting_ranges: list[tuple[date, date]],
    thin_setting_ranges: list[tuple[date, date]],
    partner_data_gap_ranges_by_protagonist: dict[str, list[tuple[date, date]]],
) -> None:
    if missing_character_ranges:
        errors.append(
            "Coverage gap: fewer than two distinct characters on "
            f"{_format_date_ranges(_coalesce_ranges(missing_character_ranges))}."
        )
    if missing_setting_ranges:
        errors.append(
            "Coverage gap: no available settings on "
            f"{_format_date_ranges(_coalesce_ranges(missing_setting_ranges))}."
        )
    if thin_character_ranges:
        warnings.append(
            "Fragile coverage: exactly two characters available on "
            f"{_format_date_ranges(_coalesce_ranges(thin_character_ranges))}."
        )
    if thin_setting_ranges:
        warnings.append(
            "Fragile coverage: exactly one setting available on "
            f"{_format_date_ranges(_coalesce_ranges(thin_setting_ranges))}."
        )
    for protagonist in sorted(partner_data_gap_ranges_by_protagonist):
        gap_ranges = _coalesce_ranges(partner_data_gap_ranges_by_protagonist[protagonist])
        warnings.append(
            "Partner data coverage gap: protagonist "
            f"'{protagonist}' has no partner era data available on "
            f"{_format_date_ranges(gap_ranges)}."
        )


def _append_prompt_depth_warnings(data: dict[str, Any], *, warnings: list[str]) -> None:
    for key in PROMPT_LIST_KEYS:
        options = data[key]
        if len(options) >= 3:
            continue
        warnings.append(
            f"Prompt depth warning: {key} has only {len(options)} option(s); "
            "consider adding at least 3 for variety."
        )

    if len(data["word_count_targets"]) < 3:
        warnings.append(
            "Prompt depth warning: word_count_targets has fewer than 3 options; "
            "consider adding more range variety."
        )


def lint_story_data(data: dict[str, Any]) -> DatasetLintReport:
    """Report actionable dataset diagnostics and coverage gaps."""
    range_start = data["date_start"]
    range_end = data["date_end"]
    sorted_checkpoints = _build_lint_checkpoints(
        data, range_start=range_start, range_end=range_end
    )
    (
        missing_character_ranges,
        thin_character_ranges,
        missing_setting_ranges,
        thin_setting_ranges,
        partner_data_gap_ranges_by_protagonist,
    ) = _collect_interval_lint_ranges(
        data, sorted_checkpoints=sorted_checkpoints, range_end=range_end
    )

    errors: list[str] = []
    warnings: list[str] = []
    _append_coverage_messages(
        errors=errors,
        warnings=warnings,
        missing_character_ranges=missing_character_ranges,
        thin_character_ranges=thin_character_ranges,
        missing_setting_ranges=missing_setting_ranges,
        thin_setting_ranges=thin_setting_ranges,
        partner_data_gap_ranges_by_protagonist=partner_data_gap_ranges_by_protagonist,
    )

    tokens_seen: set[str] = set()
    for template in data["titles"]:
        tokens_seen.update(TITLE_TOKEN_PATTERN.findall(template))
    missing_title_tokens = sorted({"protagonist", "setting", "time_period"} - tokens_seen)
    if missing_title_tokens:
        warnings.append(
            "Title coverage gap: token(s) never used in templates: "
            f"{', '.join(f'@{token}' for token in missing_title_tokens)}."
        )

    _append_prompt_depth_warnings(data, warnings=warnings)

    return DatasetLintReport(errors=errors, warnings=warnings)


def _emit_lint_report(report: DatasetLintReport) -> None:
    if report.errors:
        print("Dataset lint: errors")
        for message in report.errors:
            print(f"  - {message}")
    else:
        print("Dataset lint: no blocking coverage gaps found.")

    if report.warnings:
        print("Dataset lint: warnings")
        for message in report.warnings:
            print(f"  - {message}")
    else:
        print("Dataset lint: no warnings.")


def pick_story_fields(
    rng: random.Random | secrets.SystemRandom,
    selected_date: date | None = None,
    data: StoryData | None = None,
) -> dict[str, str | int | list[str] | None]:
    """Pick a randomized, schema-compatible story brief field set."""
    resolved_data = get_data() if data is None else data
    if selected_date is None:
        selected_date = random_date_in_range(
            rng, resolved_data["date_start"], resolved_data["date_end"]
        )
    elif not (resolved_data["date_start"] <= selected_date <= resolved_data["date_end"]):
        raise ValueError(
            f"Date {selected_date.isoformat()} is outside available range "
            f"({resolved_data['date_start'].isoformat()} "
            f"to {resolved_data['date_end'].isoformat()}). "
            "Try a date within the Commuted archive timeline."
        )
    time_period = selected_date.isoformat()

    characters_for_date = stable_sorted_pool(available_characters(selected_date, resolved_data))
    if len(characters_for_date) < 2:
        raise ValueError(
            "Need at least two distinct available characters for year "
            f"{selected_date.year}."
        )

    settings_for_date = stable_sorted_pool(available_settings(selected_date, resolved_data))
    if not settings_for_date:
        raise ValueError(
            f"No settings are available for year {selected_date.year}. "
            "Check setting availability data."
        )

    protagonist = rng.choice(characters_for_date)
    eligible_secondary = [name for name in characters_for_date if name != protagonist]
    if not eligible_secondary:
        raise ValueError(
            "Need at least two distinct available characters for year "
            f"{selected_date.year}."
        )
    secondary_character = rng.choice(eligible_secondary)
    setting = rng.choice(settings_for_date)
    title_template = rng.choice(sorted_pool_from_data(resolved_data, "titles"))
    sexual_content_level = weighted_choice(
        rng, resolved_data["sexual_content_options"], resolved_data["sexual_content_weights"]
    )
    sexual_scene_tags: list[str] = []
    if sexual_content_level != "none":
        if "sexual_scene_tag_group_names_sorted" in resolved_data:
            tag_group_names = resolved_data["sexual_scene_tag_group_names_sorted"]
        else:
            tag_group_names = stable_sorted_pool(resolved_data["sexual_scene_tag_groups"])
        tag_count_options = [
            count
            for count in SEXUAL_SCENE_TAG_COUNT_OPTIONS
            if count <= len(tag_group_names)
        ]
        tag_count_weights = [
            SEXUAL_SCENE_TAG_COUNT_WEIGHT_BY_OPTION[count] for count in tag_count_options
        ]
        selected_tag_count = int(
            weighted_choice(
                rng,
                [str(value) for value in tag_count_options],
                tag_count_weights,
            )
        )
        selected_tag_groups = rng.sample(tag_group_names, selected_tag_count)
        tag_groups_sorted = resolved_data.get("sexual_scene_tag_groups_sorted", {})
        sexual_scene_tags = [
            rng.choice(
                tag_groups_sorted[group_name]
                if group_name in tag_groups_sorted
                else stable_sorted_pool(resolved_data["sexual_scene_tag_groups"][group_name])
            )
            for group_name in selected_tag_groups
        ]

    sexual_partner: str | None = None
    if sexual_content_level != "none":
        # Validation ensures this key exists for all configured characters, but tests
        # frequently monkeypatch partial datasets. Defaulting to empty keeps those
        # cases deterministic and avoids surfacing KeyError from internal access.
        for era in resolved_data[PARTNER_DISTRIBUTIONS_KEY].get(protagonist, ()):
            if era["date_start"] <= selected_date <= era["date_end"]:
                if era["partners"]:
                    sorted_partner_pairs = stable_sorted_pool(era["partners"])
                    partner_options, partner_weights = map(list, zip(*sorted_partner_pairs))
                    sexual_partner = weighted_choice(
                        rng,
                        partner_options,
                        partner_weights,
                    )
                break

    result: dict[str, str | int | list[str] | None] = {
        "title": render_title(
            title_template,
            protagonist=protagonist,
            setting=setting,
            time_period=time_period,
        ),
        "protagonist": protagonist,
        "secondary_character": secondary_character,
        "time_period": time_period,
        "setting": setting,
        "weather": weighted_choice(
            rng,
            resolved_data["weather"],
            symmetric_peak_weights(len(resolved_data["weather"])),
        ),
        "central_conflict": rng.choice(
            sorted_pool_from_data(resolved_data, "central_conflicts")
        ),
        "inciting_pressure": rng.choice(
            sorted_pool_from_data(resolved_data, "inciting_pressures")
        ),
        "ending_type": rng.choice(sorted_pool_from_data(resolved_data, "ending_types")),
        "style_guidance": rng.choice(sorted_pool_from_data(resolved_data, "style_guidance")),
        "sexual_content_level": sexual_content_level,
        "sexual_partner": sexual_partner,
        "sexual_scene_tags": sexual_scene_tags,
        "word_count_target": rng.choice(
            sorted_pool_from_data(resolved_data, "word_count_targets")
        ),
    }
    return result


def to_markdown(
    fields: dict[str, str | int | list[str] | None],
    data: StoryData | None = None,
) -> str:
    """Render selected story fields as Markdown with YAML front matter."""
    resolved_data = get_data() if data is None else data
    ordered_fields = {key: fields[key] for key in resolved_data["ordered_keys"]}
    yaml_text = yaml.safe_dump(
        ordered_fields,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()

    body = [
        "---",
        yaml_text,
        "---",
        "",
        resolved_data["writing_preamble"],
        "",
        f"# {escape_markdown_heading_text(str(fields['title']))}",
        "",
        "## Story Draft",
        "",
        (
            f"*Write a story of approximately {fields['word_count_target']} words "
            "using the YAML brief above.*"
        ),
        "",
    ]
    return "\n".join(body)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a random story brief Markdown file with YAML front matter."
        )
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="output/story-seeds",
        help="Directory where the markdown file will be written.",
    )
    parser.add_argument(
        "--filename", help="Optional explicit filename for the markdown file."
    )
    parser.add_argument(
        "--seed", type=int, help="Optional random seed for reproducible output."
    )
    parser.add_argument(
        "--date",
        help="Optional explicit date in YYYY-MM-DD for reproducible scenario testing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the generated markdown to the terminal and do not write a file.",
    )
    parser.add_argument(
        "--validate-strict",
        action="store_true",
        help=(
            "Run strict per-date validation across the configured date range before generating "
            "output."
        ),
    )
    parser.add_argument(
        "--lint-dataset",
        action="store_true",
        help=(
            "Run dataset lint diagnostics (coverage gaps + fragile spots) and exit "
            "without generating output."
        ),
    )
    args = parser.parse_args()
    try:
        data = _get_data_cached() if args.lint_dataset else get_data()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    rng: random.Random | secrets.SystemRandom
    if args.seed is None:
        rng = secrets.SystemRandom()
    else:
        rng = random.Random(args.seed)

    if args.lint_dataset:
        report = lint_story_data(data)
        _emit_lint_report(report)
        if report.has_errors:
            raise SystemExit(1)
        return
    if args.validate_strict:
        try:
            validate_story_data_strict(data)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    selected_date: date | None = None
    if args.date:
        try:
            selected_date = date.fromisoformat(args.date)
        except ValueError as exc:
            raise SystemExit("--date must be in YYYY-MM-DD format") from exc

    try:
        fields = pick_story_fields(rng, selected_date=selected_date, data=data)
        markdown = to_markdown(fields, data=data)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if args.print_only:
        print(markdown)
        return

    trusted_base_dir = Path.cwd().resolve(strict=True)
    try:
        requested_output_dir = _build_safe_relative_path(
            args.output_dir,
            trusted_base_dir=trusted_base_dir,
        )
    except ValueError as exc:
        raise SystemExit(f"Invalid --output-dir: {exc}") from exc
    output_dir = (trusted_base_dir / requested_output_dir).resolve(strict=False)
    if not output_dir.is_relative_to(trusted_base_dir):
        raise SystemExit(
            f"--output-dir must be within {trusted_base_dir}: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.filename:
        try:
            _validate_user_filename_input(args.filename)
        except ValueError as exc:
            raise SystemExit(f"Invalid --filename: {exc}") from exc
        filename = sanitize_filename(args.filename)
    else:
        filename = build_auto_filename(
            str(fields["title"]),
            today=str(fields["time_period"]),
        )

    safe_relative_output = _build_safe_relative_path(
        str(requested_output_dir / filename),
        trusted_base_dir=trusted_base_dir,
    )
    output_path = trusted_base_dir / safe_relative_output
    resolved_output_parent = output_path.parent.resolve(strict=False)
    candidate_output_path = resolved_output_parent / output_path.name
    if not candidate_output_path.is_relative_to(trusted_base_dir):
        raise SystemExit("Resolved output path must be within the trusted base directory.")
    _write_output_markdown(candidate_output_path, markdown, force=args.force)
    print("Generated story brief.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
