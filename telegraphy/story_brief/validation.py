"""Backward-compatible validation facade.

Validation logic is split across:
- schema_validation.py (schema and config checks)
- availability_validation.py (availability parsing/window semantics)
- generation_invariants.py (strict per-date generation preconditions)
"""

from .generation_invariants import validate_story_data_strict
from .schema_validation import (
    EXPECTED_GENERATED_FIELD_KEYS,
    MAX_SEXUAL_SCENE_TAG_GROUPS,
    ValidatedStoryData,
    validate_story_data,
)

__all__ = [
    "EXPECTED_GENERATED_FIELD_KEYS",
    "MAX_SEXUAL_SCENE_TAG_GROUPS",
    "ValidatedStoryData",
    "validate_story_data",
    "validate_story_data_strict",
]
