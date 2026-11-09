from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from telegraphy.gui.preview import brief_preview
from telegraphy.gui.tablet_app import TelegraphyTablet


def test_preview_formats_fields_without_losing_instructions() -> None:
    markdown = (
        "---\ntitle: A signal\ntime_period: '2000-01-01'\nword_count_target: 2000\n"
        "protagonist: Alex\nsexual_partner: null\nsexual_scene_tags: []\n"
        "details: [quiet, tense]\n---\n\nKeep the ending open."
    )
    preview = brief_preview(markdown)
    assert preview.startswith("# A signal\n\n2000-01-01 · 2000 words")
    assert "Protagonist: Alex" in preview
    assert "## Sexual partner\n\nNone" in preview
    assert "## Sexual scene tags\n\nNone" in preview
    assert "## Details\n\nquiet, tense" in preview
    assert "Keep the ending open." in preview


@pytest.mark.parametrize(
    "markdown",
    [
        "plain text",
        "",
        "---\nmissing boundary",
        "---\n[invalid\n---",
        "---\n[]\n---",
        "---\n1: value\n---",
    ],
)
def test_preview_preserves_unrecognized_output(markdown: str) -> None:
    assert brief_preview(markdown) == markdown


def test_preview_supports_an_empty_metadata_object() -> None:
    assert brief_preview("---\n{}\n---").startswith("# Story brief")


def test_display_removes_heading_gaps_and_keeps_section_tags_aligned() -> None:
    app = MagicMock(spec=TelegraphyTablet)
    app.output = MagicMock()
    text = (
        "# Title\n\nMetadata\n\n## Characters & setting\n\n \n"
        "Protagonist: Alex\n\n## Conflict\n\nAn oath."
    )

    TelegraphyTablet._set_output(app, text)

    app.output.insert.assert_called_once_with(
        "1.0",
        "Title\n\nMetadata\n\nCharacters & setting\nProtagonist: Alex\n\nConflict\nAn oath.",
    )
    assert app.output.tag_add.call_args_list == [
        (("title", "1.0", "1.end"),),
        (("heading", "5.0", "5.end"),),
        (("heading", "8.0", "8.end"),),
    ]
