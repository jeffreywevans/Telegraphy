#!/usr/bin/env python3
"""Generate a random story brief as Markdown with YAML front matter."""

from __future__ import annotations

import random
import secrets
from copy import deepcopy
from datetime import date
from typing import Any, TypedDict

from . import data_io as _data_io_module
from ._constants import (
    CHARACTER_AVAILABILITY_KEY,
    PARTNER_DISTRIBUTIONS_KEY,
    PROMPT_LIST_KEYS,
    SETTING_AVAILABILITY_KEY,
)
from .filenames import build_auto_filename as _build_auto_filename
from .generation import (
    available_characters as _available_characters,
)
from .generation import (
    available_settings as _available_settings,
)
from .generation import (
    pick_story_fields as _pick_story_fields,
)
from .generation import (
    random_date_in_range as _random_date_in_range,
)
from .generation import (
    stable_sorted_pool,
)
from .linting import emit_lint_report as _emit_lint_report_impl
from .rendering import to_markdown as _to_markdown
from .validation import (
    EXPECTED_GENERATED_FIELD_KEYS as _EXPECTED_GENERATED_FIELD_KEYS,
)
from .validation import validate_story_data

EXPECTED_GENERATED_FIELD_KEYS = frozenset(_EXPECTED_GENERATED_FIELD_KEYS)

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


def load_story_data() -> StoryData:
    """Load, validate, and normalize the story dataset used by the generator."""
    dataset_payloads = _data_io_module.get_data()
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


def _get_data_cached() -> StoryData:
    """Compatibility wrapper for callers expecting a cached getter."""
    return load_story_data()


def _clear_get_data_cache() -> None:
    _data_io_module.clear_data_cache()


def clear_get_data_cache() -> None:
    """Clear the authoritative raw dataset cache in data_io."""
    _clear_get_data_cache()


def get_data() -> StoryData:
    """Load story-brief data from the authoritative data_io cache.

    Returns a deep copy of processed data to prevent cache poisoning when callers
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


def random_date_in_range(
    rng: random.Random | secrets.SystemRandom, start: date, end: date
) -> date:
    """Return a random date between start and end (inclusive)."""
    return _random_date_in_range(rng, start, end)


def available_characters(
    selected_date: date, data: dict[str, Any] | None = None
) -> list[str]:
    """Return characters available for the selected date."""
    resolved_data = get_data() if data is None else data
    return _available_characters(selected_date, resolved_data)


def available_settings(
    selected_date: date, data: dict[str, Any] | None = None
) -> list[str]:
    """Return settings available for the selected date."""
    resolved_data = get_data() if data is None else data
    return _available_settings(selected_date, resolved_data)



def pick_story_fields(
    rng: random.Random | secrets.SystemRandom,
    selected_date: date | None = None,
    data: StoryData | None = None,
) -> dict[str, str | int | list[str] | None]:
    """Pick a randomized, schema-compatible story brief field set."""
    resolved_data = get_data() if data is None else data
    return _pick_story_fields(rng, selected_date=selected_date, data=resolved_data)


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


def build_auto_filename(title: str, *, today: str | None = None) -> str:
    """Compatibility wrapper for filename generation helper."""
    return _build_auto_filename(title, today=today)


def _emit_lint_report(report: Any) -> None:
    """Compatibility wrapper for legacy lint-report emission helper."""
    _emit_lint_report_impl(report)


def main() -> None:
    """Compatibility wrapper that delegates CLI orchestration to ``cli.py``."""
    from .cli import main as _cli_main
    exit_code = _cli_main()
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
