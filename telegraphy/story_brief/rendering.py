from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

import yaml

from ._constants import TITLE_TOKEN_PATTERN

_ISO_DATE_SCALAR_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[ tT]\d{2}:\d{2}:\d{2})?$",
    re.ASCII,
)

if TYPE_CHECKING:

    class _SafeDumperBase:
        @classmethod
        def add_representer(cls, data_type: type[object], representer: Any) -> None: ...

        def represent_scalar(
            self, tag: str, value: str, style: str | None = None
        ) -> yaml.ScalarNode: ...

else:
    _SafeDumperBase = yaml.SafeDumper


class _StoryBriefDumper(_SafeDumperBase):
    """Safe dumper with stable scalar rendering for front matter."""


def _represent_story_scalar(dumper: _StoryBriefDumper, value: str) -> yaml.ScalarNode:
    """Quote ISO-like date strings to prevent implicit YAML date coercion."""
    style = "'" if _ISO_DATE_SCALAR_PATTERN.fullmatch(value) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_StoryBriefDumper.add_representer(str, _represent_story_scalar)


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


def escape_markdown_heading(text: str) -> str:
    """Escape Markdown-significant characters for safe heading rendering."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!])", r"\\\1", text)


def _format_yaml_list(values: Sequence[str]) -> list[str]:
    """YAML list serializer hook for future list-shaping behavior."""
    return [str(value) for value in values]


def to_markdown(
    fields: Mapping[str, Any],
    *,
    ordered_keys: Sequence[str],
    writing_preamble: str,
) -> str:
    """Render selected story fields as Markdown with YAML front matter."""
    missing_keys = [key for key in ordered_keys if key not in fields]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ValueError(f"Missing required field keys for Markdown rendering: {missing}")

    ordered_fields: dict[str, Any] = {}
    for key in ordered_keys:
        value = fields[key]
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            ordered_fields[key] = _format_yaml_list(value)
        else:
            ordered_fields[key] = value

    yaml_text = yaml.dump(
        ordered_fields,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        Dumper=_StoryBriefDumper,
    ).strip()

    body = [
        "---",
        yaml_text,
        "---",
        "",
        writing_preamble,
        "",
        f"# {escape_markdown_heading(str(fields.get('title', 'Untitled Story Brief')))}",
        "",
        "## Story Draft",
        "",
        (
            f"*Write a story of approximately {fields.get('word_count_target', 'N/A')} words "
            "using the YAML brief above.*"
        ),
        "",
    ]
    return "\n".join(body)
