"""Backward-compatible validation facade.

Validation logic is split across:
- schema_validation.py (schema and config checks)
- availability_validation.py (availability parsing/window semantics)
- generation_invariants.py (strict per-date generation preconditions)
"""

from .generation_invariants import validate_story_data_strict
from .schema_validation import (
    ValidatedStoryData,
    validate_story_data,
)
from .schema_validation_config import (
    EXPECTED_GENERATED_FIELD_KEYS,
    MAX_SEXUAL_SCENE_TAG_GROUPS,
    UNSUPPORTED_CONFIG_ALIAS_ERROR_PREFIX,
    UNSUPPORTED_CONFIG_ALIAS_KEYS,
)

__all__ = [
    "EXPECTED_GENERATED_FIELD_KEYS",
    "MAX_SEXUAL_SCENE_TAG_GROUPS",
    "UNSUPPORTED_CONFIG_ALIAS_ERROR_PREFIX",
    "UNSUPPORTED_CONFIG_ALIAS_KEYS",
    "ValidatedStoryData",
    "validate_story_data",
    "validate_story_data_strict",
]
