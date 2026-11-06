"""Readable brief previews; clipboard content remains the original Markdown."""

from __future__ import annotations

from typing import Final

import yaml

_CHARACTER_KEYS: Final = ("protagonist", "secondary_character", "setting", "weather")
_HEADER_KEYS: Final = frozenset(("title", "time_period", "word_count_target", *_CHARACTER_KEYS))


def brief_preview(markdown: str) -> str:
    """Expand YAML front matter into labeled prose, falling back to the original text."""
    parsed = _front_matter(markdown)
    if parsed is None:
        return markdown
    fields, body = parsed
    title = str(fields.get("title") or "Story brief")
    preview = [f"# {title}", _metadata(fields)]
    characters = [
        f"{key.replace('_', ' ').capitalize()}: {_display_value(fields[key])}"
        for key in _CHARACTER_KEYS
        if key in fields
    ]
    if characters:
        preview.extend(("## Characters & setting", "\n".join(characters)))
    for key, value in fields.items():
        if key not in _HEADER_KEYS:
            label = key.replace("_", " ").capitalize()
            preview.extend((f"## {label}", _display_value(value)))
    if body:
        preview.extend(("## Writing instructions", body))
    return "\n\n".join(preview)


def _front_matter(markdown: str) -> tuple[dict[str, object], str] | None:
    """Read only well-formed object front matter; leave other output untouched."""
    lines = markdown.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        boundary = lines.index("---", 1)
        fields = yaml.safe_load("\n".join(lines[1:boundary]))
    except ValueError, yaml.YAMLError, RecursionError:
        return None
    if not isinstance(fields, dict) or any(not isinstance(key, str) for key in fields):
        return None
    return fields, "\n".join(lines[boundary + 1 :]).strip()


def _metadata(fields: dict[str, object]) -> str:
    metadata = [str(fields[key]) for key in ("time_period",) if key in fields]
    if "word_count_target" in fields:
        metadata.append(f"{fields['word_count_target']} words")
    return " · ".join(metadata)


def _display_value(value: object) -> str:
    """Keep optional and collection values readable without discarding their contents."""
    if value is None:
        return "None"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "None"
    return str(value)
