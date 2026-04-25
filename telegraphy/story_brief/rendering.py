from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

import yaml

TITLE_TOKEN_PATTERN = re.compile(r"@(?P<key>protagonist|setting|time_period)\b")


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


def _format_yaml_value(value: Any) -> Any:
    """YAML serializer passthrough hook for future focused formatting behavior."""
    return value


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
    ordered_fields: dict[str, Any] = {}
    for key in ordered_keys:
        value = _format_yaml_value(fields.get(key))
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            ordered_fields[key] = _format_yaml_list(value)
        else:
            ordered_fields[key] = value

    yaml_text = yaml.safe_dump(
        ordered_fields,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
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
