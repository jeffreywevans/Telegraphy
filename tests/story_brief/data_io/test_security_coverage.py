from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path

import pytest

from telegraphy.story_brief import data_io


class _FakeTraversable:
    def __init__(self) -> None:
        self.requested: str | None = None

    def joinpath(self, filename: str) -> str:
        self.requested = filename
        return f"resource://{filename}"


class _NameAsObjectTraversable:
    def __init__(self, name: object) -> None:
        self.name = name


def test_expand_home_marker_accepts_bare_home() -> None:
    assert data_io._expand_home_marker("~") == str(Path.home())


def test_expand_home_marker_accepts_windows_style_home_prefix() -> None:
    expected = str(Path.home() / "dataset")
    assert data_io._expand_home_marker(r"~\dataset") == expected


def test_override_rejects_named_user_home_expansion() -> None:
    with pytest.raises(data_io.DataDirError, match="must not use ~user expansion"):
        data_io._validated_override_path_text("~other-user/story-data")


def test_data_file_rejects_unknown_filename() -> None:
    with pytest.raises(ValueError, match="Refusing to open unknown data file"):
        data_io._data_file_from_dir(Path.cwd(), "../titles.json")


def test_data_file_rejects_case_variant_of_allowed_filename() -> None:
    with pytest.raises(ValueError, match="Refusing to open unknown data file"):
        data_io._data_file_from_dir(Path.cwd(), "TITLES.JSON")


def test_validated_override_path_rejects_backslash_parent_traversal() -> None:
    with pytest.raises(data_io.DataDirError, match="parent-directory traversal"):
        data_io._validated_override_path_text(r"/tmp/story-data\..\escape")


def test_data_file_uses_traversable_joinpath() -> None:
    traversable = _FakeTraversable()

    result = data_io._data_file_from_dir(traversable, "titles.json")

    assert result == "resource://titles.json"
    assert traversable.requested == "titles.json"


def test_contained_child_path_rejects_resolved_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_resolve = Path.resolve
    outside = tmp_path.parent / "outside" / "titles.json"

    def fake_resolve(self: Path, *, strict: bool = False) -> Path:
        if self.name == "titles.json":
            return outside
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", fake_resolve)

    with pytest.raises(data_io.DataDirError, match="escapes the data directory"):
        data_io._contained_child_path(tmp_path, "titles.json")


def test_contained_child_path_rejects_non_directory_base(tmp_path: Path) -> None:
    base_file = tmp_path / "not-a-directory"
    base_file.write_text("x", encoding="utf-8")

    with pytest.raises(data_io.DataDirError, match="must be an existing directory"):
        data_io._contained_child_path(base_file, "titles.json")


def test_load_data_reports_configured_missing_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "story-data"
    data_dir.mkdir()
    monkeypatch.setenv(data_io.DATA_DIR_ENV_VAR, str(data_dir))

    with pytest.raises(data_io.DataDirError) as exc_info:
        data_io.load_data()

    message = str(exc_info.value)
    assert "file 'titles.json'" in message
    assert "configured data directory" in message


def test_data_file_rejects_extremely_long_unicode_filename() -> None:
    long_unicode_name = ("あ" * 90) + ".json"
    assert len(long_unicode_name.encode("utf-8")) > 255

    with pytest.raises(ValueError, match="Refusing to open unknown data file"):
        data_io._data_file_from_dir(Path.cwd(), long_unicode_name)


def test_data_file_rejects_unicode_normalization_variant_that_collides() -> None:
    decomposed = unicodedata.normalize("NFD", "títles.json")
    composed = unicodedata.normalize("NFC", "títles.json")
    assert decomposed != composed
    assert unicodedata.normalize("NFC", decomposed).casefold() == composed.casefold()

    with pytest.raises(ValueError, match="non-canonical data file"):
        data_io._data_file_from_dir(Path.cwd(), decomposed)


def test_load_json_uses_o_nofollow_for_paths_from_fallback_data_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_dir = tmp_path / "story-data"
    data_dir.mkdir()
    for filename in data_io.DATA_FILENAMES.values():
        (data_dir / filename).write_text(json.dumps({}), encoding="utf-8")

    opened_flags: list[int] = []
    real_open = os.open

    def recording_open(path: str | os.PathLike[str], flags: int, mode: int = 0o777) -> int:
        opened_flags.append(flags)
        return real_open(path, flags, mode)

    monkeypatch.setattr(data_io, "_fallback_data_dir", lambda: data_dir)
    monkeypatch.setattr(
        data_io,
        "files",
        lambda _resource: (_ for _ in ()).throw(TypeError("boom")),
    )
    monkeypatch.setattr(data_io.os, "open", recording_open)

    data_io.load_data(data_io.resolve_data_dir())
    assert opened_flags
    if hasattr(os, "O_NOFOLLOW"):
        assert all(flags & os.O_NOFOLLOW for flags in opened_flags)


def test_load_json_closes_fd_when_fdopen_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload_path = tmp_path / "payload.json"
    payload_path.write_text("{}", encoding="utf-8")

    recorded: dict[str, int] = {}
    real_open = os.open
    real_close = os.close

    def recording_open(path: str | os.PathLike[str], flags: int, mode: int = 0o777) -> int:
        fd = real_open(path, flags, mode)
        recorded["fd"] = fd
        return fd

    def recording_close(fd: int) -> None:
        recorded["closed_fd"] = fd
        real_close(fd)

    def exploding_fdopen(*_args: object, **_kwargs: object) -> object:
        raise OSError("fdopen failed")

    monkeypatch.setattr(data_io.os, "open", recording_open)
    monkeypatch.setattr(data_io.os, "close", recording_close)
    monkeypatch.setattr(data_io.os, "fdopen", exploding_fdopen)

    with pytest.raises(OSError, match="fdopen failed"):
        data_io._load_json(payload_path)

    assert "fd" in recorded
    assert recorded.get("closed_fd") == recorded["fd"]


def test_validated_load_path_rejects_nul_bytes_for_traversable_name() -> None:
    traversable = _NameAsObjectTraversable("titles\x00.json")

    with pytest.raises(ValueError, match="NUL bytes"):
        data_io._validated_load_path(traversable)


def test_validated_load_path_rejects_parent_traversal_for_traversable_name() -> None:
    traversable = _NameAsObjectTraversable("../titles.json")

    with pytest.raises(ValueError, match="parent-directory traversal"):
        data_io._validated_load_path(traversable)


def test_validated_load_path_rejects_non_absolute_path_instance() -> None:
    with pytest.raises(ValueError, match="non-absolute filesystem path"):
        data_io._validated_load_path(Path("relative.json"))


def test_validated_load_path_coerces_non_string_name_attribute() -> None:
    traversable = _NameAsObjectTraversable(12345)

    assert data_io._validated_load_path(traversable) is traversable
