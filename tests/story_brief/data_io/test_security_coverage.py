from __future__ import annotations

from pathlib import Path

import pytest

from telegraphy.story_brief import data_io


class _FakeTraversable:
    def __init__(self) -> None:
        self.requested: str | None = None

    def joinpath(self, filename: str) -> str:
        self.requested = filename
        return f"resource://{filename}"


def test_expand_home_marker_accepts_bare_home() -> None:
    assert data_io._expand_home_marker("~") == str(Path.home())


def test_override_rejects_named_user_home_expansion() -> None:
    with pytest.raises(data_io.DataDirError, match="must not use ~user expansion"):
        data_io._validated_override_path_text("~other-user/story-data")


def test_data_file_rejects_unknown_filename() -> None:
    with pytest.raises(ValueError, match="Refusing to open unknown data file"):
        data_io._data_file_from_dir(Path.cwd(), "../titles.json")


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

    with pytest.raises(ValueError) as exc_info:
        data_io.load_data()

    message = str(exc_info.value)
    assert "file 'titles.json'" in message
    assert "configured data directory" in message
