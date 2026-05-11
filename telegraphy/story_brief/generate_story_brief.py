#!/usr/bin/env python3
"""Generate a random story brief as Markdown with YAML front matter."""

from __future__ import annotations

import random
import secrets
from datetime import date

from ._constants import (
    CHARACTER_AVAILABILITY_KEY,
    PARTNER_DISTRIBUTIONS_KEY,
    SETTING_AVAILABILITY_KEY,
)
from .data_io import DATA_FILENAMES, clear_data_cache, get_data, get_normalized_story_data
from .filenames import build_auto_filename
from .generation import pick_story_fields as _pick_story_fields
from .linting import emit_lint_report
from .rendering import to_markdown as _to_markdown
from .schema_validation_config import EXPECTED_GENERATED_FIELD_KEYS
from .story_data import NormalizedPartnerEra, StoryData


# Public exports for this module.
__all__ = [
    "CHARACTER_AVAILABILITY_KEY",
    "DATA_FILENAMES",
    "EXPECTED_GENERATED_FIELD_KEYS",
    "NormalizedPartnerEra",
    "PARTNER_DISTRIBUTIONS_KEY",
    "SETTING_AVAILABILITY_KEY",
    "StoryData",
    "build_auto_filename",
    "clear_data_cache",
    "emit_lint_report",
    "get_data",
    "get_normalized_story_data",
    "pick_story_fields",
    "to_markdown",
]

def pick_story_fields(
    rng: random.Random | secrets.SystemRandom,
    selected_date: date | None = None,
    data: StoryData | None = None,
) -> dict[str, str | int | list[str] | None]:
    """Pick a randomized, schema-compatible story brief field set."""
    resolved_data = get_normalized_story_data() if data is None else data
    return _pick_story_fields(rng, selected_date=selected_date, data=resolved_data)


def to_markdown(
    fields: dict[str, str | int | list[str] | None],
    data: StoryData | None = None,
) -> str:
    """Render selected story fields as Markdown with YAML front matter."""
    resolved_data = get_normalized_story_data() if data is None else data
    return _to_markdown(
        fields,
        ordered_keys=resolved_data["ordered_keys"],
        writing_preamble=resolved_data["writing_preamble"],
    )
