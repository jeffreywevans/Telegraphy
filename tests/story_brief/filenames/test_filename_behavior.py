from __future__ import annotations

import os
import stat
from datetime import date, datetime
from pathlib import Path

import pytest

from telegraphy.story_brief.filenames import (
    OutputPathError,
    OutputWriteError,
    _apply_windows_reserved_name_guard,
    _build_safe_relative_path,
    _open_temporary_output_file,
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


def test_sanitize_filename_retruncates_fallback_stem_after_post_truncation_recovery() -> None:
    sanitized = sanitize_filename(f" a.{'b' * 253}")
    assert len(sanitized.encode("utf-8")) <= 255
    assert sanitized.startswith("s.")


def test_build_auto_filename_uses_fallback_slug_for_empty_slugified_title() -> None:
    assert build_auto_filename("!!!", today=datetime(2026, 4, 21)) == "2026-04-21 story-brief.md"


def test_build_auto_filename_accepts_date_for_today() -> None:
    assert (
        build_auto_filename("Hello World", today=date(2026, 4, 21)) == "2026-04-21 hello-world.md"
    )


def test_build_auto_filename_accepts_iso_date_string_for_today() -> None:
    assert build_auto_filename("Hello World", today="2026-04-21") == "2026-04-21 hello-world.md"


def test_resolve_output_path_does_not_create_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = Path("nested") / "missing"

    resolved = resolve_output_path(
        output_dir=output_dir,
        filename="brief.md",
        generated_filename="fallback.md",
    )

    assert resolved == tmp_path / "nested" / "missing" / "brief.md"
    assert not (tmp_path / "nested" / "missing").exists()


def test_write_output_markdown_accepts_absolute_path_within_base(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "brief.md"
    output_path.parent.mkdir(parents=True)

    write_output_markdown(
        output_path=output_path,
        content="hello",
        trusted_base_dir=tmp_path,
    )

    assert output_path.read_text(encoding="utf-8") == "hello"


def test_write_output_markdown_rejects_absolute_path_outside_base(tmp_path: Path) -> None:
    outside_path = tmp_path.parent / "outside-brief.md"

    with pytest.raises(OutputPathError, match="trusted base directory"):
        write_output_markdown(
            output_path=outside_path,
            content="hello",
            trusted_base_dir=tmp_path,
        )


def test_write_output_markdown_refuses_symbolic_link_output(tmp_path: Path) -> None:
    symlink_target = tmp_path / "target.md"
    symlink_target.write_text("existing", encoding="utf-8")
    output_path = tmp_path / "brief.md"
    output_path.symlink_to(symlink_target)

    with pytest.raises(OutputWriteError, match="symbolic-link output path"):
        write_output_markdown(
            output_path=output_path,
            content="replacement",
            trusted_base_dir=tmp_path,
        )

    assert symlink_target.read_text(encoding="utf-8") == "existing"


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
        "run.sh",
        "brief",
        "brief.md.txt",
    ],
)
def test_validate_user_filename_input_rejects_unsafe_values(filename: str) -> None:
    with pytest.raises(ValueError):
        _validate_user_filename_input(filename)


@pytest.mark.parametrize("filename", ["brief.md", "BRIEF.MD"])
def test_validate_user_filename_input_accepts_markdown_extension(filename: str) -> None:
    _validate_user_filename_input(filename)


def test_build_safe_relative_path_rejects_home_and_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must not begin with '~'"):
        _build_safe_relative_path("~/docs", trusted_base_dir=tmp_path)
    with pytest.raises(ValueError, match="must not include parent-directory traversal"):
        _build_safe_relative_path("../docs", trusted_base_dir=tmp_path)


def test_build_safe_relative_path_accepts_absolute_inside_base(tmp_path: Path) -> None:
    nested = tmp_path / "safe" / "area"
    assert _build_safe_relative_path(str(nested), trusted_base_dir=tmp_path) == Path("safe/area")


def test_build_safe_relative_path_maps_blank_to_current_directory(tmp_path: Path) -> None:
    assert _build_safe_relative_path("   ", trusted_base_dir=tmp_path) == Path(".")


def test_build_safe_relative_path_rejects_absolute_path_outside_base(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside"
    with pytest.raises(ValueError, match="must remain inside the base directory"):
        _build_safe_relative_path(str(outside), trusted_base_dir=tmp_path)


def test_resolve_output_path_uses_generated_filename_when_filename_not_supplied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    resolved = resolve_output_path(
        output_dir=Path("reports"),
        filename=None,
        generated_filename="auto.md",
    )
    assert resolved == tmp_path / "reports" / "auto.md"


def test_resolve_output_path_reports_invalid_output_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(OutputPathError, match="Invalid --output-dir"):
        resolve_output_path(
            output_dir=Path("~/unsafe"),
            filename="brief.md",
            generated_filename="auto.md",
        )


def test_resolve_output_path_reports_invalid_filename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(OutputPathError, match="Invalid --filename"):
        resolve_output_path(
            output_dir=Path("safe"),
            filename="bad/name.md",
            generated_filename="auto.md",
        )


def test_resolve_output_path_rejects_non_markdown_filename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(OutputPathError, match=r"filename must use the \.md extension"):
        resolve_output_path(
            output_dir=Path("safe"),
            filename="run.sh",
            generated_filename="auto.md",
        )


def test_resolve_output_path_reports_invalid_output_filename_path_combination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(OutputPathError, match="Invalid output filename/path combination"):
        resolve_output_path(
            output_dir=Path("safe"),
            filename=None,
            generated_filename="../escape.md",
        )


def test_write_output_markdown_force_overwrites_existing_file(tmp_path: Path) -> None:
    output_path = tmp_path / "brief.md"
    output_path.write_text("old", encoding="utf-8")

    write_output_markdown(
        output_path=output_path,
        content="new",
        force=True,
        trusted_base_dir=tmp_path,
    )

    assert output_path.read_text(encoding="utf-8") == "new"


@pytest.mark.skipif(os.name == "nt", reason="POSIX umask and permission modes")
@pytest.mark.parametrize(
    ("file_umask", "expected_mode"),
    [(0o077, 0o600), (0o022, 0o644), (0o002, 0o664), (0o000, 0o666)],
)
def test_write_output_markdown_honors_umask(
    tmp_path: Path,
    file_umask: int,
    expected_mode: int,
) -> None:
    output_path = tmp_path / f"brief-{file_umask:03o}.md"
    previous_umask = os.umask(file_umask)
    try:
        write_output_markdown(
            output_path=output_path,
            content="content",
            trusted_base_dir=tmp_path,
        )
    finally:
        os.umask(previous_umask)

    assert stat.S_IMODE(output_path.stat().st_mode) == expected_mode


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission modes")
def test_write_output_markdown_force_preserves_existing_mode(tmp_path: Path) -> None:
    output_path = tmp_path / "shared.md"
    output_path.write_text("old", encoding="utf-8")
    output_path.chmod(0o640)

    previous_umask = os.umask(0o077)
    try:
        write_output_markdown(
            output_path=output_path,
            content="new",
            force=True,
            trusted_base_dir=tmp_path,
        )
    finally:
        os.umask(previous_umask)

    assert output_path.read_text(encoding="utf-8") == "new"
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o640


def test_open_temporary_output_file_retries_random_name_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collision = tmp_path / ".telegraphy-collision.tmp"
    collision.write_text("occupied", encoding="utf-8")
    tokens = iter(("collision", "available"))
    monkeypatch.setattr(
        "telegraphy.story_brief.filenames.secrets.token_hex",
        lambda _size: next(tokens),
    )

    fd, temporary_path = _open_temporary_output_file(tmp_path)
    os.close(fd)
    temporary_path.unlink()

    assert temporary_path.name == ".telegraphy-available.tmp"


def test_write_output_markdown_preserves_existing_file_when_atomic_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "brief.md"
    output_path.write_text("old", encoding="utf-8")

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("telegraphy.story_brief.filenames.os.replace", fail_replace)

    with pytest.raises(OutputWriteError, match="replace failed"):
        write_output_markdown(
            output_path=output_path,
            content="new",
            force=True,
            trusted_base_dir=tmp_path,
        )

    assert output_path.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob(".telegraphy-*.tmp")) == []


def test_write_output_markdown_does_not_mask_error_when_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "brief.md"
    cleanup_attempts: list[Path] = []

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("replace failed")

    def fail_cleanup(path: Path, *, missing_ok: bool = False) -> None:
        cleanup_attempts.append(path)
        raise OSError("cleanup failed")

    monkeypatch.setattr("telegraphy.story_brief.filenames.os.replace", fail_replace)
    monkeypatch.setattr(Path, "unlink", fail_cleanup)

    with pytest.raises(OutputWriteError, match="replace failed"):
        write_output_markdown(
            output_path=output_path,
            content="new",
            force=True,
            trusted_base_dir=tmp_path,
        )

    assert len(cleanup_attempts) == 1


def test_write_output_markdown_refuses_existing_file_without_force(tmp_path: Path) -> None:
    output_path = tmp_path / "brief.md"
    output_path.write_text("existing", encoding="utf-8")

    with pytest.raises(OutputWriteError, match="Refusing to overwrite existing file"):
        write_output_markdown(
            output_path=output_path,
            content="new",
            trusted_base_dir=tmp_path,
        )


def test_write_output_markdown_wraps_oserror(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "brief.md"

    def fake_open(*_args: object, **_kwargs: object) -> int:
        raise OSError("disk error")

    monkeypatch.setattr("telegraphy.story_brief.filenames.os.open", fake_open)

    with pytest.raises(OutputWriteError, match="Unable to safely open or write output path"):
        write_output_markdown(
            output_path=target,
            content="content",
            trusted_base_dir=tmp_path,
        )


def test_write_output_markdown_closes_descriptor_when_fdopen_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "brief.md"
    closed_descriptors: list[int] = []
    original_close = os.close

    def fail_fdopen(*_args: object, **_kwargs: object) -> None:
        raise OSError("fdopen failed")

    def record_close(fd: int) -> None:
        closed_descriptors.append(fd)
        original_close(fd)

    monkeypatch.setattr("telegraphy.story_brief.filenames.os.fdopen", fail_fdopen)
    monkeypatch.setattr("telegraphy.story_brief.filenames.os.close", record_close)

    with pytest.raises(OutputWriteError, match="fdopen failed"):
        write_output_markdown(
            output_path=target,
            content="content",
            trusted_base_dir=tmp_path,
        )

    assert len(closed_descriptors) == 1
    assert list(tmp_path.glob(".telegraphy-*.tmp")) == []


def test_write_output_markdown_without_onofollow_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "brief.md"
    captured_flags: list[int] = []
    original_open = os.open

    monkeypatch.delattr("telegraphy.story_brief.filenames.os.O_NOFOLLOW", raising=False)

    def fake_open(path: str, flags: int, mode: int) -> int:
        captured_flags.append(flags)
        return original_open(path, flags, mode)

    monkeypatch.setattr("telegraphy.story_brief.filenames.os.open", fake_open)

    write_output_markdown(
        output_path=target,
        content="content",
        trusted_base_dir=tmp_path,
    )

    assert captured_flags
