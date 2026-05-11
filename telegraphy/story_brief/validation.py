"""Backward-compatible validation exports for story brief datasets."""

from __future__ import annotations

from .generation_invariants import validate_story_data_strict
from .schema_validation import validate_story_data
from .schema_validation_config import (
    EXPECTED_GENERATED_FIELD_KEYS as _EXPECTED_GENERATED_FIELD_KEYS,
)
from .schema_validation_config import (
    MAX_SEXUAL_SCENE_TAG_GROUPS,
    UNSUPPORTED_CONFIG_ALIAS_ERROR_PREFIX,
    UNSUPPORTED_CONFIG_ALIAS_KEYS,
)

EXPECTED_GENERATED_FIELD_KEYS = set(_EXPECTED_GENERATED_FIELD_KEYS)


__all__ = [
    "EXPECTED_GENERATED_FIELD_KEYS",
    "MAX_SEXUAL_SCENE_TAG_GROUPS",
    "UNSUPPORTED_CONFIG_ALIAS_ERROR_PREFIX",
    "UNSUPPORTED_CONFIG_ALIAS_KEYS",
    "validate_story_data",
    "validate_story_data_strict",
]
