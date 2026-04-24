from __future__ import annotations

from datetime import date, datetime

from telegraphy.story_brief.generate_story_brief import (
    build_auto_filename,
    sanitize_filename,
)


def test_sanitize_filename_handles_invalid_chars_and_reserved_names() -> None:
    assert sanitize_filename("../bad:name?.md") == "bad-name-.md"
    assert sanitize_filename("CON") == "CON-file"
    assert sanitize_filename("   .md") == "story-brief.md"


def test_build_auto_filename_uses_fallback_slug_for_empty_slugified_title() -> None:
    assert (
        build_auto_filename("!!!", today=datetime(2026, 4, 21))
        == "2026-04-21 story-brief.md"
    )


def test_build_auto_filename_accepts_date_for_today() -> None:
    assert (
        build_auto_filename("Hello World", today=date(2026, 4, 21))
        == "2026-04-21 hello-world.md"
    )


def test_build_auto_filename_accepts_iso_date_string_for_today() -> None:
    assert (
        build_auto_filename("Hello World", today="2026-04-21")
        == "2026-04-21 hello-world.md"
    )
