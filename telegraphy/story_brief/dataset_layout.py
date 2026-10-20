"""Physical field files and their assembly into the existing validation sections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

FILE_LAYOUT_SCHEMA_VERSION: Final = 2


@dataclass(frozen=True)
class FieldFile:
    """One editable field dataset and its destination in the validation pipeline."""

    section: str
    required_keys: tuple[str, ...]
    optional_keys: tuple[str, ...] = ()


FIELD_FILES: Final[dict[str, FieldFile]] = {
    "titles": FieldFile("titles", ("titles",)),
    "characters": FieldFile("entities", ("character_availability",)),
    "time_period": FieldFile("config", ("date_start", "date_end")),
    "settings": FieldFile("entities", ("setting_availability",)),
    "weather": FieldFile("weather", ("weather",), ("weather_comment",)),
    "central_conflicts": FieldFile("prompts", ("central_conflicts",)),
    "inciting_pressures": FieldFile("prompts", ("inciting_pressures",)),
    "ending_types": FieldFile("prompts", ("ending_types",)),
    "style_guidance": FieldFile("prompts", ("style_guidance",)),
    "sexual_content_levels": FieldFile(
        "config", ("sexual_content_presence_options", "sexual_content_presence_weights")
    ),
    "sexual_partners": FieldFile(
        "partner_distributions",
        ("schema_version", "dataset_version", "date_start", "date_end", "partner_distributions"),
        ("model_definition", "counting_policy", "placeholder_partner_keys"),
    ),
    "sexual_scene_tags": FieldFile(
        "config",
        (
            "sexual_scene_tag_groups",
            "sexual_scene_tag_count_weights_by_presence",
            "sexual_scene_required_tag_groups_by_presence",
        ),
        ("sexual_scene_optional_tag_groups",),
    ),
    "word_count_targets": FieldFile("config", ("word_count_targets",)),
    "config": FieldFile("config", ("schema_version", "dataset_version", "ordered_keys")),
    "writing_preamble": FieldFile("config", ("writing_preamble",)),
}

DATA_FILENAMES: Final[dict[str, str]] = {key: f"{key}.json" for key in FIELD_FILES}


def assemble_dataset_sections(payloads: Mapping[str, object]) -> dict[str, dict[str, object]]:
    """Validate file ownership and combine fields for cross-field validation.

    The combined sections exist only in memory. The on-disk format has one
    source of truth for each field, including its weights and selection rules.
    """
    sections: dict[str, dict[str, object]] = {}
    for name, definition in FIELD_FILES.items():
        filename = DATA_FILENAMES[name]
        payload = payloads.get(name)
        if not isinstance(payload, dict):
            raise ValueError(f"{filename}: expected a JSON object")
        if not all(isinstance(key, str) for key in payload):
            raise ValueError(f"{filename}: object keys must be strings")
        missing = sorted(set(definition.required_keys) - payload.keys())
        if missing:
            raise ValueError(f"{filename}: missing required keys: {', '.join(missing)}")
        allowed_keys = set(definition.required_keys) | set(definition.optional_keys)
        unexpected = sorted(payload.keys() - allowed_keys)
        if unexpected:
            raise ValueError(f"{filename}: unexpected keys: {', '.join(unexpected)}")
        if name == "config":
            _validate_layout_version(payload["schema_version"])
        sections.setdefault(definition.section, {}).update(payload)
    return sections


def _validate_layout_version(version: object) -> None:
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != FILE_LAYOUT_SCHEMA_VERSION
    ):
        raise ValueError(
            "config.json: unsupported schema_version; "
            f"expected {FILE_LAYOUT_SCHEMA_VERSION} for the field-file layout"
        )
