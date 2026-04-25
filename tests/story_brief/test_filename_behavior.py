from __future__ import annotations

from datetime import date, datetime

from telegraphy.story_brief.filenames import sanitize_filename
from telegraphy.story_brief.generate_story_brief import build_auto_filename


def test_sanitize_filename_handles_invalid_chars_and_reserved_names() -> None:
    assert sanitize_filename("../bad:name?.md") == "bad-name.md"
    assert sanitize_filename("CON") == "CON-file"
    assert sanitize_filename("   .md") == "story-brief.md"


def test_sanitize_filename_trims_stem_length_and_reapplies_fallback() -> None:
    assert sanitize_filename(f"{'a' * 140}.md") == f"{'a' * 120}.md"
    assert sanitize_filename("?.md") == "story-brief.md"


def test_sanitize_filename_caps_total_utf8_byte_length() -> None:
    filename = sanitize_filename(f"{'😀' * 120}.md")
    assert len(filename.encode("utf-8")) <= 255
    assert filename.endswith(".md")


def test_sanitize_filename_trims_suffix_when_needed() -> None:
    sanitized = sanitize_filename(f"{'a' * 120}.{'b' * 300}")
    assert len(sanitized.encode("utf-8")) <= 255


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
