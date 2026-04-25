from __future__ import annotations

import sys
from pathlib import Path

import pytest

from telegraphy.story_brief import cli as story_cli
from telegraphy.story_brief import filenames as filename_utils


def test_main_print_only_calls_pick_story_fields_with_selected_date(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured_date = None

    def fake_pick_story_fields(
        _rng: object,
        *,
        selected_date: object = None,
        data: object = None,
    ) -> dict[str, object]:
        nonlocal captured_date
        captured_date = selected_date
        return {"title": "Sample", "word_count_target": 900}

    monkeypatch.setattr(sys, "argv", ["story-brief", "--date", "2001-02-03", "--print-only"])
    monkeypatch.setattr(story_cli._legacy_cli, "pick_story_fields", fake_pick_story_fields)
    monkeypatch.setattr(
        story_cli._legacy_cli,
        "to_markdown",
        lambda _fields, data=None: "---\nmock\n---",
    )

    assert story_cli.main() == 0

    output = capsys.readouterr().out
    assert output == "---\nmock\n---\n"
    assert captured_date
    assert captured_date.isoformat() == "2001-02-03"


def test_main_lint_dataset_exits_early_without_generating_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Report:
        has_errors = False

    called = {"lint": 0, "emit": 0, "pick": 0}

    def fake_lint(_data: object) -> _Report:
        called["lint"] += 1
        return _Report()

    monkeypatch.setattr(sys, "argv", ["story-brief", "--lint-dataset"])
    monkeypatch.setattr(story_cli._legacy_cli, "_get_data_cached", lambda: {"source": "test"})
    monkeypatch.setattr(story_cli, "lint_story_data", fake_lint)
    monkeypatch.setattr(
        story_cli,
        "emit_lint_report",
        lambda _: called.__setitem__("emit", called["emit"] + 1),
    )
    monkeypatch.setattr(
        story_cli._legacy_cli,
        "pick_story_fields",
        lambda *_args, **_kwargs: called.__setitem__("pick", called["pick"] + 1),
    )

    assert story_cli.main() == 0

    assert called == {"lint": 1, "emit": 1, "pick": 0}


def test_main_force_flag_allows_overwrite_for_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_file = tmp_path / "forced.md"
    output_file.write_text("old-content", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "story-brief",
            "-o",
            str(tmp_path),
            "--filename",
            "forced.md",
            "--force",
        ],
    )
    monkeypatch.setattr(
        story_cli._legacy_cli, "pick_story_fields", lambda *_args, **_kwargs: {"title": "Forced"}
    )
    monkeypatch.setattr(
        story_cli._legacy_cli,
        "to_markdown",
        lambda _fields, data=None: "new-content",
    )

    assert story_cli.main() == 0

    assert output_file.read_text(encoding="utf-8") == "new-content"


def test_main_lint_dataset_with_errors_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Report:
        has_errors = True

    monkeypatch.setattr(sys, "argv", ["story-brief", "--lint-dataset"])
    monkeypatch.setattr(story_cli._legacy_cli, "_get_data_cached", lambda: {})
    monkeypatch.setattr(story_cli, "lint_story_data", lambda _data: _Report())
    monkeypatch.setattr(story_cli, "emit_lint_report", lambda _report: None)

    assert story_cli.main() == 1


def test_main_validate_strict_failure_exits_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_fail(_data: object) -> None:
        raise ValueError("Strict validation failed: boom")

    monkeypatch.setattr(sys, "argv", ["story-brief", "--validate-strict", "--print-only"])
    monkeypatch.setattr(story_cli._legacy_cli, "_get_data_cached", lambda: {})
    monkeypatch.setattr(story_cli, "validate_story_data_strict", mock_fail)

    assert story_cli.main() == 1


def test_main_pick_story_fields_failure_exits_with_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_fail(*_args: object, **_kwargs: object) -> None:
        raise ValueError("Need at least two")

    monkeypatch.setattr(sys, "argv", ["story-brief", "--print-only"])
    monkeypatch.setattr(story_cli._legacy_cli, "pick_story_fields", mock_fail)

    assert story_cli.main() == 1


def test_main_rejects_parent_traversal_in_output_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["story-brief", "--output-dir", "../outside", "--filename", "safe.md"],
    )
    monkeypatch.setattr(
        story_cli._legacy_cli, "pick_story_fields", lambda *_args, **_kwargs: {"title": "A"}
    )
    monkeypatch.setattr(story_cli._legacy_cli, "to_markdown", lambda _fields, data=None: "body")

    assert story_cli.main() == 1


def test_main_allows_absolute_output_dir_when_within_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "nested" / "safe"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["story-brief", "--output-dir", str(output_dir), "--filename", "safe.md"],
    )
    monkeypatch.setattr(
        story_cli._legacy_cli, "pick_story_fields", lambda *_args, **_kwargs: {"title": "A"}
    )
    monkeypatch.setattr(story_cli._legacy_cli, "to_markdown", lambda _fields, data=None: "body")

    assert story_cli.main() == 0

    assert (output_dir / "safe.md").read_text(encoding="utf-8") == "body"


def test_main_force_rejects_symlink_output_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not hasattr(filename_utils.os, "O_NOFOLLOW"):
        pytest.skip("Platform does not expose O_NOFOLLOW")

    output_dir = tmp_path / "output" / "story-seeds"
    output_dir.mkdir(parents=True)
    target = tmp_path / "outside.md"
    link_name = output_dir / "linked.md"
    target.write_text("seed", encoding="utf-8")
    link_name.symlink_to(target)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        sys,
        "argv",
        ["story-brief", "--filename", "linked.md", "--force"],
    )
    monkeypatch.setattr(
        story_cli._legacy_cli, "pick_story_fields", lambda *_args, **_kwargs: {"title": "A"}
    )
    monkeypatch.setattr(story_cli._legacy_cli, "to_markdown", lambda _fields, data=None: "body")

    assert story_cli.main() == 1


def test_main_write_failure_exits_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["story-brief", "--filename", "write-fail.md", "--force"],
    )
    monkeypatch.setattr(
        story_cli._legacy_cli, "pick_story_fields", lambda *_args, **_kwargs: {"title": "A"}
    )
    monkeypatch.setattr(story_cli._legacy_cli, "to_markdown", lambda _fields, data=None: "body")

    real_open = filename_utils.os.open

    def fake_open(path: object, flags: int, mode: int) -> int:
        return real_open(path, flags, mode)

    def fake_fdopen(fd: int, *_args: object, **_kwargs: object) -> object:
        filename_utils.os.close(fd)
        raise OSError("No space left on device")

    monkeypatch.setattr(filename_utils.os, "open", fake_open)
    monkeypatch.setattr(filename_utils.os, "fdopen", fake_fdopen)

    assert story_cli.main() == 1


def test_main_returns_zero_for_help_flag_without_raising() -> None:
    assert story_cli.main(["--help"]) == 0


def test_main_returns_two_for_unknown_flag_without_raising() -> None:
    assert story_cli.main(["--unknown"]) == 2
