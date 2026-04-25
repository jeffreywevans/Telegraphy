#!/usr/bin/env python3
"""Generate a random story brief as Markdown with YAML front matter."""

from __future__ import annotations

import argparse
import math
import random
import re
import secrets
from copy import deepcopy
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, NamedTuple, Sequence, TypedDict, TypeVar

if __package__ in (None, ""):
    import data_io as _data_io_module
    from filenames import (
        DEFAULT_OUTPUT_DIR,
        OutputPathError,
        OutputWriteError,
        resolve_output_path,
        sanitize_filename,
        write_output_markdown as _write_output_markdown,
    )
    from rendering import (
        escape_markdown_heading as escape_markdown_heading_text,
        render_title,
        to_markdown as _to_markdown,
    )
    from validation import (
        validate_story_data,
        validate_story_data_strict,
    )
else:
    from . import data_io as _data_io_module
    from .filenames import (
        DEFAULT_OUTPUT_DIR,
        OutputPathError,
        OutputWriteError,
        resolve_output_path,
        sanitize_filename,
        write_output_markdown as _write_output_markdown,
    )
    from .rendering import (
        escape_markdown_heading as escape_markdown_heading_text,
        render_title,
        to_markdown as _to_markdown,
    )
    from .validation import (
        validate_story_data,
        validate_story_data_strict,
    )

PoolValue = TypeVar("PoolValue", str, int)

TITLE_TOKEN_PATTERN = re.compile(r"@(?P<key>protagonist|setting|time_period)\b")
DEFAULT_SEXUAL_SCENE_TAG_COUNT_WEIGHT_BY_OPTION = {
    2: 0.7,
    3: 0.1,
    4: 0.1,
    5: 0.1,
}
PROMPT_LIST_KEYS = (
    "central_conflicts",
    "inciting_pressures",
    "ending_types",
    "style_guidance",
    "weather",
)
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


class DatasetLintReport(NamedTuple):
    errors: list[str]
    warnings: list[str]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


class _IntervalLintResults(NamedTuple):
    missing_character_ranges: list[tuple[date, date]]
    thin_character_ranges: list[tuple[date, date]]
    missing_setting_ranges: list[tuple[date, date]]
    thin_setting_ranges: list[tuple[date, date]]
    partner_data_gap_ranges_by_protagonist: dict[str, list[tuple[date, date]]]


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
    sexual_scene_tag_count_options: tuple[int, ...]
    sexual_scene_tag_count_weights: tuple[float, ...]
    word_count_targets: tuple[int, ...]
    word_count_targets_sorted: tuple[int, ...]
    ordered_keys: tuple[str, ...]
    writing_preamble: str
    dataset_version: str
    partner_distributions: dict[str, tuple[dict[str, Any], ...]]


def _data_file(filename: str) -> Any:
    """Compatibility wrapper for data file resolution."""
    return _data_io_module._data_file(filename)


def _load_json(path: Any) -> dict[str, Any]:
    """Compatibility wrapper for JSON loading."""
    return _data_io_module._load_json(path)


def load_story_data() -> StoryData:
    """Load, validate, and normalize the story dataset used by the generator."""
    dataset_payloads = _data_io_module.load_data()
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
    sorted_items = sorted(
        config["sexual_scene_tag_count_weights"].items(),
        key=lambda item: int(item[0]),
    )
    options_str, weights_raw = zip(*sorted_items)
    sexual_scene_tag_count_options = tuple(map(int, options_str))
    sexual_scene_tag_count_weights = tuple(map(float, weights_raw))

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
        "sexual_scene_tag_count_options": sexual_scene_tag_count_options,
        "sexual_scene_tag_count_weights": sexual_scene_tag_count_weights,
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


def build_auto_filename(title: str, today: date | datetime | str | None = None) -> str:
    """Build a sanitized default filename with a non-empty slug fallback."""
    slug = slugify(title) or "story-brief"
    if isinstance(today, str):
        date_prefix = today
    else:
        date_prefix = (today or datetime.now()).strftime("%Y-%m-%d")
    return sanitize_filename(f"{date_prefix} {slug}.md")


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

    # Avoid random.choices: it consumes RNG differently and breaks seed-stable generation.
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
) -> _IntervalLintResults:
    one_day = timedelta(days=1)
    missing_character_ranges: list[tuple[date, date]] = []
    thin_character_ranges: list[tuple[date, date]] = []
    missing_setting_ranges: list[tuple[date, date]] = []
    thin_setting_ranges: list[tuple[date, date]] = []
    partner_data_gap_ranges_by_protagonist: dict[str, list[tuple[date, date]]] = {}

    for index, current_start in enumerate(sorted_checkpoints):
        next_start = (
            sorted_checkpoints[index + 1]
            if index + 1 < len(sorted_checkpoints)
            else (range_end + one_day if range_end < date.max else None)
        )
        interval_end = range_end if next_start is None else min(range_end, next_start - one_day)
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

    return _IntervalLintResults(
        missing_character_ranges=missing_character_ranges,
        thin_character_ranges=thin_character_ranges,
        missing_setting_ranges=missing_setting_ranges,
        thin_setting_ranges=thin_setting_ranges,
        partner_data_gap_ranges_by_protagonist=partner_data_gap_ranges_by_protagonist,
    )


def _append_coverage_messages(
    *,
    errors: list[str],
    warnings: list[str],
    interval_results: _IntervalLintResults,
) -> None:
    if interval_results.missing_character_ranges:
        errors.append(
            "Coverage gap: fewer than two distinct characters on "
            f"{_format_date_ranges(_coalesce_ranges(interval_results.missing_character_ranges))}."
        )
    if interval_results.missing_setting_ranges:
        errors.append(
            "Coverage gap: no available settings on "
            f"{_format_date_ranges(_coalesce_ranges(interval_results.missing_setting_ranges))}."
        )
    if interval_results.thin_character_ranges:
        warnings.append(
            "Fragile coverage: exactly two characters available on "
            f"{_format_date_ranges(_coalesce_ranges(interval_results.thin_character_ranges))}."
        )
    if interval_results.thin_setting_ranges:
        warnings.append(
            "Fragile coverage: exactly one setting available on "
            f"{_format_date_ranges(_coalesce_ranges(interval_results.thin_setting_ranges))}."
        )
    for protagonist in sorted(interval_results.partner_data_gap_ranges_by_protagonist):
        gap_ranges = _coalesce_ranges(
            interval_results.partner_data_gap_ranges_by_protagonist[protagonist]
        )
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
    interval_results = _collect_interval_lint_ranges(
        data, sorted_checkpoints=sorted_checkpoints, range_end=range_end
    )

    errors: list[str] = []
    warnings: list[str] = []
    _append_coverage_messages(
        errors=errors,
        warnings=warnings,
        interval_results=interval_results,
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
        configured_tag_count_pairs = list(
            zip(
                resolved_data.get(
                    "sexual_scene_tag_count_options",
                    tuple(DEFAULT_SEXUAL_SCENE_TAG_COUNT_WEIGHT_BY_OPTION),
                ),
                resolved_data.get(
                    "sexual_scene_tag_count_weights",
                    tuple(DEFAULT_SEXUAL_SCENE_TAG_COUNT_WEIGHT_BY_OPTION.values()),
                ),
            )
        )
        tag_count_options: list[int] = []
        tag_count_weights: list[float] = []
        for count, weight in configured_tag_count_pairs:
            if count <= len(tag_group_names):
                tag_count_options.append(count)
                tag_count_weights.append(weight)
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
    return _to_markdown(
        fields,
        ordered_keys=resolved_data["ordered_keys"],
        writing_preamble=resolved_data["writing_preamble"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a random story brief Markdown file with YAML front matter."
        )
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
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

    generated_filename = build_auto_filename(
        str(fields["title"]),
        today=str(fields.get("time_period", date.today().isoformat())),
    )
    try:
        candidate_output_path = resolve_output_path(
            Path(args.output_dir),
            args.filename,
            generated_filename,
        )
        candidate_output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_output_markdown(candidate_output_path, markdown, force=args.force)
    except OutputPathError as exc:
        raise SystemExit(str(exc)) from exc
    except OutputWriteError as exc:
        raise SystemExit(str(exc)) from exc
    except OSError as exc:
        raise SystemExit(f"Error creating output directory: {exc}") from exc
    print("Generated story brief.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
