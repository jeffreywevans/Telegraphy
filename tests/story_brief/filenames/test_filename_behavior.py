from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from telegraphy.story_brief.filenames import (
    OutputPathError,
    OutputWriteError,
    _apply_windows_reserved_name_guard,
    _build_safe_relative_path,
    _truncate_utf8_filename,
    _validate_user_filename_input,
    resolve_output_path,
    sanitize_filename,
    write_output_markdown,
)
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


def test_resolve_output_path_does_not_create_directories(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = Path("nested") / "missing"

    resolved = resolve_output_path(
        output_dir=output_dir,
        filename="brief.md",
        generated_filename="fallback.md",
    )

    assert resolved == tmp_path / "nested" / "missing" / "brief.md"
    assert not (tmp_path / "nested" / "missing").exists()


def test_write_output_markdown_accepts_absolute_path_within_base(tmp_path) -> None:
    output_path = tmp_path / "nested" / "brief.md"
    output_path.parent.mkdir(parents=True)

    write_output_markdown(
        output_path=output_path,
        content="hello",
        trusted_base_dir=tmp_path,
    )

    assert output_path.read_text(encoding="utf-8") == "hello"


def test_write_output_markdown_rejects_absolute_path_outside_base(tmp_path) -> None:
    outside_path = tmp_path.parent / "outside-brief.md"

    with pytest.raises(OutputPathError, match="trusted base directory"):
        write_output_markdown(
            output_path=outside_path,
            content="hello",
            trusted_base_dir=tmp_path,
        )


def test_truncate_utf8_filename_returns_empty_for_non_positive_max_bytes() -> None:
    assert _truncate_utf8_filename("name", ".md", max_bytes=0) == ""


def test_truncate_utf8_filename_returns_suffix_when_suffix_exhausts_budget() -> None:
    assert _truncate_utf8_filename("name", ".markdown", max_bytes=4) == ".mar"


def test_apply_windows_reserved_name_guard_falls_back_to_file() -> None:
    stem, suffix = _apply_windows_reserved_name_guard("con", "." + ("a" * 251))
    assert stem.startswith("fil")
    assert stem.casefold() not in {"con", "prn", "aux", "nul"}
    assert suffix.startswith(".")


def test_apply_windows_reserved_name_guard_keeps_non_reserved_names() -> None:
    stem, suffix = _apply_windows_reserved_name_guard("brief", ".md")
    assert stem == "brief"
    assert suffix == ".md"


@pytest.mark.parametrize(
    "filename",
    [
        "",
        " trailing ",
        "bad/name.md",
        "bad\\name.md",
        ".hidden.md",
        "..",
        "name..md",
    ],
)
def test_validate_user_filename_input_rejects_unsafe_values(filename: str) -> None:
    with pytest.raises(ValueError):
        _validate_user_filename_input(filename)


def test_build_safe_relative_path_rejects_home_and_traversal(tmp_path) -> None:
    with pytest.raises(ValueError, match="must not begin with '~'"):
        _build_safe_relative_path("~/docs", trusted_base_dir=tmp_path)
    with pytest.raises(ValueError, match="must not include parent-directory traversal"):
        _build_safe_relative_path("../docs", trusted_base_dir=tmp_path)


def test_build_safe_relative_path_accepts_absolute_inside_base(tmp_path) -> None:
    nested = tmp_path / "safe" / "area"
    assert _build_safe_relative_path(str(nested), trusted_base_dir=tmp_path) == Path("safe/area")


def test_build_safe_relative_path_maps_blank_to_current_directory(tmp_path) -> None:
    assert _build_safe_relative_path("   ", trusted_base_dir=tmp_path) == Path(".")


def test_build_safe_relative_path_rejects_absolute_path_outside_base(tmp_path) -> None:
    outside = tmp_path.parent / "outside"
    with pytest.raises(ValueError, match="must remain inside the base directory"):
        _build_safe_relative_path(str(outside), trusted_base_dir=tmp_path)


def test_resolve_output_path_uses_generated_filename_when_filename_not_supplied(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    resolved = resolve_output_path(
        output_dir=Path("reports"),
        filename=None,
        generated_filename="auto.md",
    )
    assert resolved == tmp_path / "reports" / "auto.md"


def test_resolve_output_path_reports_invalid_output_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(OutputPathError, match="Invalid --output-dir"):
        resolve_output_path(
            output_dir=Path("~/unsafe"),
            filename="brief.md",
            generated_filename="auto.md",
        )


def test_resolve_output_path_reports_invalid_filename(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(OutputPathError, match="Invalid --filename"):
        resolve_output_path(
            output_dir=Path("safe"),
            filename="bad/name.md",
            generated_filename="auto.md",
        )


def test_resolve_output_path_reports_invalid_output_filename_path_combination(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(OutputPathError, match="Invalid output filename/path combination"):
        resolve_output_path(
            output_dir=Path("safe"),
            filename=None,
            generated_filename="../escape.md",
        )


def test_write_output_markdown_force_overwrites_existing_file(tmp_path) -> None:
    output_path = tmp_path / "brief.md"
    output_path.write_text("old", encoding="utf-8")

    write_output_markdown(
        output_path=output_path,
        content="new",
        force=True,
        trusted_base_dir=tmp_path,
    )

    assert output_path.read_text(encoding="utf-8") == "new"


def test_write_output_markdown_refuses_existing_file_without_force(tmp_path) -> None:
    output_path = tmp_path / "brief.md"
    output_path.write_text("existing", encoding="utf-8")

    with pytest.raises(OutputWriteError, match="Refusing to overwrite existing file"):
        write_output_markdown(
            output_path=output_path,
            content="new",
            trusted_base_dir=tmp_path,
        )


def test_write_output_markdown_wraps_oserror(monkeypatch, tmp_path) -> None:
    target = tmp_path / "brief.md"

    def fake_open(*_args, **_kwargs):
        raise OSError("disk error")

    monkeypatch.setattr("telegraphy.story_brief.filenames.os.open", fake_open)

    with pytest.raises(OutputWriteError, match="Unable to safely open or write output path"):
        write_output_markdown(
            output_path=target,
            content="content",
            trusted_base_dir=tmp_path,
        )


def test_write_output_markdown_without_onofollow_when_unavailable(
    monkeypatch, tmp_path
) -> None:
    import os

    target = tmp_path / "brief.md"
    captured_flags: list[int] = []
    original_open = os.open

    monkeypatch.delattr("telegraphy.story_brief.filenames.os.O_NOFOLLOW", raising=False)

    def fake_open(path, flags, mode):
        captured_flags.append(flags)
        return original_open(path, flags, mode)

    monkeypatch.setattr("telegraphy.story_brief.filenames.os.open", fake_open)

    write_output_markdown(
        output_path=target,
        content="content",
        trusted_base_dir=tmp_path,
    )

    assert captured_flags
