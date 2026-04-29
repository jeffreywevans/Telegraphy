from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
ENTRYPOINT = "telegraphy.story_brief"
CLI_TIMEOUT_SECONDS = 20


def assert_cli_error_without_traceback(
    result: subprocess.CompletedProcess[str], expected_message: str
) -> None:
    """Assert a CLI command failed with a user-facing error and no traceback."""
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert expected_message in combined
    assert "Traceback" not in combined


def make_single_character_single_setting_dataset(
    data_dir: Path,
    patch_json: Callable[[Path, str, Callable[[dict[str, object]], object]], None],
) -> None:
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


def remove_prompt_key(
    data_dir: Path,
    key: str,
    patch_json: Callable[[Path, str, Callable[[dict[str, object]], object]], None],
) -> None:
    """Remove a prompt key from prompts.json."""
    patch_json(data_dir, "prompts.json", lambda prompts: prompts.pop(key))


def run_cli(
    *args: str,
    cwd: Path,
    data_dir: Path | None = None,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("TELEGRAPHY_DATA_DIR", None)
    if data_dir is not None:
        env["TELEGRAPHY_DATA_DIR"] = str(data_dir)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", ENTRYPOINT, *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=CLI_TIMEOUT_SECONDS,
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
    cli_dataset_factory: Callable[[str], Path],
    patch_json: Callable[[Path, str, Callable[[dict[str, object]], object]], None],
    tmp_path: Path,
) -> None:
    data_dir = cli_dataset_factory("lint-data")
    make_single_character_single_setting_dataset(data_dir, patch_json)

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
    cli_dataset_factory: Callable[[str], Path],
    patch_json: Callable[[Path, str, Callable[[dict[str, object]], object]], None],
    tmp_path: Path,
) -> None:
    data_dir = cli_dataset_factory("invalid-data")
    remove_prompt_key(data_dir, "weather", patch_json)

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
        data_dir=missing_dir,
    )
    assert_cli_error_without_traceback(result, "Failed to load story brief dataset file")
