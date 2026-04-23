from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from collections.abc import Callable

import pytest

from telegraphy.story_brief import generate_story_brief as story_cli
from telegraphy.story_brief.generate_story_brief import (
    build_auto_filename,
    sanitize_filename,
)
from tests.conftest import patch_json

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "telegraphy" / "story_brief" / "generate_story_brief.py"


def assert_cli_error_without_traceback(
    result: subprocess.CompletedProcess[str], expected_message: str
) -> None:
    """Assert a CLI command failed with a user-facing error and no traceback."""
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert expected_message in combined
    assert "Traceback" not in combined


def make_single_character_single_setting_dataset(data_dir: Path) -> None:
    """Mutate dataset to a single-character/single-setting configuration."""
    patch_json(
        data_dir,
        "config.json",
        lambda config: config.update({"date_start": "2000-01-01", "date_end": "2000-01-01"}),
    )
    patch_json(
        data_dir,
        "entities.json",
        lambda entities: entities.update(
            {
                "character_availability": [["Only One", "2000-01-01", "2000-01-01"]],
                "setting_availability": [["Only Place", "2000-01-01", "2000-01-01"]],
            }
        ),
    )
    patch_json(
        data_dir,
        "partner_distributions.json",
        lambda payload: payload.update(
            {
                "partner_distributions": [
                    {
                        "character": "Only One",
                        "date_start": "2000-01-01",
                        "date_end": "2000-01-01",
                        "eras": [
                            {
                                "date_start": "2000-01-01",
                                "date_end": "2000-01-01",
                                "partners": [{"partner": "Nobody", "weight": 1.0}],
                            }
                        ],
                    }
                ]
            }
        ),
    )


def remove_prompt_key(data_dir: Path, key: str) -> None:
    """Remove a prompt key from prompts.json."""
    patch_json(data_dir, "prompts.json", lambda prompts: prompts.pop(key))


def run_cli(
    *args: str,
    cwd: Path,
    data_dir: Path | None = None,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if data_dir is not None:
        env["TELEGRAPHY_DATA_DIR"] = str(data_dir)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_print_only_writes_nothing(tmp_path: Path) -> None:
    result = run_cli("--seed", "42", "--print-only", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.startswith("---\n")
    assert list(tmp_path.iterdir()) == []


def test_print_only_with_explicit_date_sets_time_period(tmp_path: Path) -> None:
    result = run_cli("--seed", "42", "--date", "2000-01-01", "--print-only", cwd=tmp_path)
    assert result.returncode == 0
    assert "time_period: '2000-01-01'" in result.stdout


def test_write_and_force_overwrite_behavior(tmp_path: Path) -> None:
    outdir = tmp_path / "out"
    filename = "brief.md"

    first = run_cli("--seed", "42", "-o", str(outdir), "--filename", filename, cwd=tmp_path)
    assert first.returncode == 0
    output_file = outdir / filename
    assert output_file.exists()

    second = run_cli("--seed", "42", "-o", str(outdir), "--filename", filename, cwd=tmp_path)
    assert second.returncode != 0
    assert "Refusing to overwrite existing file" in (second.stdout + second.stderr)

    third = run_cli(
        "--seed",
        "42",
        "-o",
        str(outdir),
        "--filename",
        filename,
        "--force",
        cwd=tmp_path,
    )
    assert third.returncode == 0


def test_default_output_dir_is_relative(tmp_path: Path) -> None:
    filename = "relative-default.md"
    result = run_cli("--seed", "42", "--filename", filename, "--force", cwd=tmp_path)
    assert result.returncode == 0
    assert (tmp_path / "output" / "story-seeds" / filename).exists()


def test_default_filename_is_auto_generated_when_omitted(tmp_path: Path) -> None:
    outdir = tmp_path / "out"
    result = run_cli("--seed", "42", "-o", str(outdir), "--force", cwd=tmp_path)
    assert result.returncode == 0

    files = list(outdir.glob("*.md"))
    assert len(files) == 1
    assert re.match(r"^\d{4}-\d{2}-\d{2} [a-z0-9-]+\.md$", files[0].name)


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
    assert build_auto_filename("Hello World", today=date(2026, 4, 21)) == "2026-04-21 hello-world.md"


def test_build_auto_filename_accepts_iso_date_string_for_today() -> None:
    assert (
        build_auto_filename("Hello World", today="2026-04-21")
        == "2026-04-21 hello-world.md"
    )


def test_default_filename_uses_story_time_period_date(tmp_path: Path) -> None:
    outdir = tmp_path / "out"
    result = run_cli("--seed", "42", "-o", str(outdir), "--force", cwd=tmp_path)
    assert result.returncode == 0

    files = list(outdir.glob("*.md"))
    assert len(files) == 1

    content = files[0].read_text(encoding="utf-8")
    match = re.search(r"time_period: '(\d{4}-\d{2}-\d{2})'", content)
    assert match is not None
    assert files[0].name.startswith(f"{match.group(1)} ")


@pytest.mark.parametrize(
    ("args", "expected_message"),
    [
        (
            ("--date", "01-01-2000", "--print-only"),
            "--date must be in YYYY-MM-DD format",
        ),
        (("--date", "1900-01-01", "--print-only"), "outside available range"),
    ],
)
def test_cli_invalid_inputs_show_user_friendly_error(
    tmp_path: Path,
    args: tuple[str, ...],
    expected_message: str,
) -> None:
    result = run_cli(*args, cwd=tmp_path)
    assert_cli_error_without_traceback(result, expected_message)


def test_cli_validate_strict_flag_accepts_current_dataset_range(tmp_path: Path) -> None:
    result = run_cli("--seed", "42", "--validate-strict", "--print-only", cwd=tmp_path)
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "Strict validation failed" not in combined
    assert "Traceback" not in combined


def test_cli_lint_dataset_flag_reports_results_and_exits_cleanly(tmp_path: Path) -> None:
    result = run_cli("--lint-dataset", cwd=tmp_path)
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "Dataset lint:" in combined
    assert "Traceback" not in combined


def test_cli_lint_dataset_takes_precedence_over_validate_strict(
    cli_dataset_factory: Callable[[str], Path], tmp_path: Path
) -> None:
    data_dir = cli_dataset_factory("lint-data")
    make_single_character_single_setting_dataset(data_dir)

    result = run_cli(
        "--validate-strict",
        "--lint-dataset",
        cwd=tmp_path,
        data_dir=data_dir,
    )
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "Dataset lint: errors" in combined
    assert "Coverage gap: fewer than two distinct characters" in combined
    assert "Strict validation failed" not in combined


def test_cli_lint_dataset_handles_invalid_dataset_without_traceback(
    cli_dataset_factory: Callable[[str], Path], tmp_path: Path
) -> None:
    data_dir = cli_dataset_factory("invalid-data")
    remove_prompt_key(data_dir, "weather")

    result = run_cli(
        "--lint-dataset",
        cwd=tmp_path,
        data_dir=data_dir,
    )
    assert_cli_error_without_traceback(result, "missing required keys")


def test_cli_handles_missing_dataset_override_without_traceback(tmp_path: Path) -> None:
    missing_dir = tmp_path / "does-not-exist"
    result = run_cli(
        "--print-only",
        cwd=tmp_path,
        env_overrides={"TELEGRAPHY_DATA_DIR": str(missing_dir)},
    )
    assert_cli_error_without_traceback(result, "Failed to load story brief dataset file")


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
    monkeypatch.setattr(story_cli, "pick_story_fields", fake_pick_story_fields)
    monkeypatch.setattr(
        story_cli,
        "to_markdown",
        lambda _fields, data=None: "---\nmock\n---",
    )

    story_cli.main()

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
    monkeypatch.setattr(story_cli, "get_data", lambda: {"source": "test"})
    monkeypatch.setattr(story_cli, "lint_story_data", fake_lint)
    monkeypatch.setattr(story_cli, "_emit_lint_report", lambda _: called.__setitem__("emit", called["emit"] + 1))
    monkeypatch.setattr(
        story_cli,
        "pick_story_fields",
        lambda *_args, **_kwargs: called.__setitem__("pick", called["pick"] + 1),
    )

    story_cli.main()

    assert called == {"lint": 1, "emit": 1, "pick": 0}


def test_main_force_flag_allows_overwrite_for_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_file = tmp_path / "forced.md"
    output_file.write_text("old-content", encoding="utf-8")

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
    monkeypatch.setattr(story_cli, "pick_story_fields", lambda *_args, **_kwargs: {"title": "Forced"})
    monkeypatch.setattr(story_cli, "to_markdown", lambda _fields, data=None: "new-content")

    story_cli.main()

    assert output_file.read_text(encoding="utf-8") == "new-content"


def test_main_lint_dataset_with_errors_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Report:
        has_errors = True

    monkeypatch.setattr(sys, "argv", ["story-brief", "--lint-dataset"])
    monkeypatch.setattr(story_cli, "_get_data_cached", lambda: {})
    monkeypatch.setattr(story_cli, "lint_story_data", lambda _data: _Report())
    monkeypatch.setattr(story_cli, "_emit_lint_report", lambda _report: None)

    with pytest.raises(SystemExit, match="1"):
        story_cli.main()


def test_main_validate_strict_failure_exits_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_fail(_data: object) -> None:
        raise ValueError("Strict validation failed: boom")

    monkeypatch.setattr(sys, "argv", ["story-brief", "--validate-strict", "--print-only"])
    monkeypatch.setattr(story_cli, "_get_data_cached", lambda: {})
    monkeypatch.setattr(story_cli, "validate_story_data_strict", mock_fail)

    with pytest.raises(SystemExit, match="Strict validation failed: boom"):
        story_cli.main()


def test_main_pick_story_fields_failure_exits_with_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_fail(*_args: object, **_kwargs: object) -> None:
        raise ValueError("Need at least two")

    monkeypatch.setattr(sys, "argv", ["story-brief", "--print-only"])
    monkeypatch.setattr(story_cli, "pick_story_fields", mock_fail)

    with pytest.raises(SystemExit, match="Need at least two"):
        story_cli.main()
