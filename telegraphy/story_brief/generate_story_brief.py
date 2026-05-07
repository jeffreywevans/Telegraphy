#!/usr/bin/env python3
"""Generate a random story brief as Markdown with YAML front matter."""

from __future__ import annotations

import random
import secrets
from datetime import date
from typing import TypedDict, cast

from . import data_io as _data_io_module
from . import filenames as _filenames
from ._constants import (
    CHARACTER_AVAILABILITY_KEY as _CHARACTER_AVAILABILITY_KEY,
)
from ._constants import (
    PARTNER_DISTRIBUTIONS_KEY as _PARTNER_DISTRIBUTIONS_KEY,
)
from ._constants import (
    SETTING_AVAILABILITY_KEY as _SETTING_AVAILABILITY_KEY,
)
from .generation import pick_story_fields as _pick_story_fields
from .linting import emit_lint_report
from .rendering import to_markdown as _to_markdown
from .validation import (
    EXPECTED_GENERATED_FIELD_KEYS as _EXPECTED_GENERATED_FIELD_KEYS,
)


class NormalizedPartnerEra(TypedDict):
    date_start: date
    date_end: date
    partners: tuple[tuple[str, float], ...]


# NOTE:
# - validation.EXPECTED_GENERATED_FIELD_KEYS is intentionally a mutable `set`
#   for internal set arithmetic in validation helpers.
# - The public re-export here is a `frozenset` to provide an immutable API.
EXPECTED_GENERATED_FIELD_KEYS = frozenset(_EXPECTED_GENERATED_FIELD_KEYS)
build_auto_filename = _filenames.build_auto_filename
CHARACTER_AVAILABILITY_KEY = _CHARACTER_AVAILABILITY_KEY
SETTING_AVAILABILITY_KEY = _SETTING_AVAILABILITY_KEY
PARTNER_DISTRIBUTIONS_KEY = _PARTNER_DISTRIBUTIONS_KEY


# Public exports for this facade module.
__all__ = [
    "CHARACTER_AVAILABILITY_KEY",
    "CONFIG_FILENAME",
    "ENTITIES_FILENAME",
    "EXPECTED_GENERATED_FIELD_KEYS",
    "NormalizedPartnerEra",
    "PARTNER_DISTRIBUTIONS_FILENAME",
    "PARTNER_DISTRIBUTIONS_KEY",
    "PROMPTS_FILENAME",
    "SETTING_AVAILABILITY_KEY",
    "STORY_DATASET_FILES",
    "StoryData",
    "TITLES_FILENAME",
    "build_auto_filename",
    "clear_get_data_cache",
    "emit_lint_report",
    "get_data",
    "load_story_data",
    "pick_story_fields",
    "to_markdown",
]


# Canonical dataset file mapping lives in telegraphy.story_brief.data_io.
STORY_DATASET_FILES = _data_io_module.DATA_FILENAMES

# Backward-compatible aliases re-exported from the canonical mapping.
TITLES_FILENAME = STORY_DATASET_FILES["titles"]
ENTITIES_FILENAME = STORY_DATASET_FILES["entities"]
PROMPTS_FILENAME = STORY_DATASET_FILES["prompts"]
CONFIG_FILENAME = STORY_DATASET_FILES["config"]
PARTNER_DISTRIBUTIONS_FILENAME = STORY_DATASET_FILES["partner_distributions"]


class StoryData(TypedDict):
    titles: tuple[str, ...]
    titles_sorted: tuple[str, ...]
    character_availability: tuple[tuple[str, date, date], ...]
    setting_availability: tuple[tuple[str, date, date], ...]
    central_conflicts: tuple[str, ...]
    inciting_pressures: tuple[str, ...]
    ending_types: tuple[str, ...]
    style_guidance: tuple[str, ...]
    weather_comment: str
    weather: tuple[str, ...]
    central_conflicts_sorted: tuple[str, ...]
    inciting_pressures_sorted: tuple[str, ...]
    ending_types_sorted: tuple[str, ...]
    style_guidance_sorted: tuple[str, ...]
    weather_sorted: tuple[str, ...]
    date_start: date
    date_end: date
    sexual_content_presence_options: tuple[str, ...]
    sexual_content_presence_weights: tuple[float, ...]
    sexual_content_story_role_options: tuple[str, ...]
    sexual_content_story_role_weights: tuple[float, ...]
    sexual_scene_tag_groups: dict[str, tuple[str, ...]]
    sexual_scene_tag_group_names_sorted: tuple[str, ...]
    sexual_scene_tag_groups_sorted: dict[str, tuple[str, ...]]
    sexual_scene_tag_count_weights_by_presence: dict[str, dict[int, float]]
    sexual_scene_required_tag_groups_by_presence: dict[str, tuple[str, ...]]
    sexual_scene_optional_tag_groups: tuple[str, ...]
    word_count_targets: tuple[int, ...]
    word_count_targets_sorted: tuple[int, ...]
    ordered_keys: tuple[str, ...]
    writing_preamble: str
    dataset_version: str
    partner_distributions: dict[str, tuple[NormalizedPartnerEra, ...]]


def get_data() -> StoryData:
    """Load story-brief data from the authoritative data_io cache.

    Returns a deep copy of processed data to prevent cache poisoning when callers
    mutate nested structures.
    """
    return cast(StoryData, _data_io_module.get_normalized_story_data())


def load_story_data() -> StoryData:
    """Backward-compatible alias for :func:`get_data`."""
    return get_data()


def _clear_get_data_cache() -> None:
    _data_io_module.clear_data_cache()


def clear_get_data_cache() -> None:
    """Clear the authoritative raw dataset cache in data_io."""
    _clear_get_data_cache()


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
