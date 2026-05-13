from __future__ import annotations

from telegraphy.gui.cli_runner import CliRunResult, build_cli_command
from telegraphy.gui.models import RunOptions, RunOptionsValidationError, resolve_run_options


def test_resolve_run_options_returns_validation_error_for_invalid_seed() -> None:
    result = resolve_run_options(
        seed_text="abc",
        date_text="",
        current_options=RunOptions(seed=2, date="2025-01-01", timeout_seconds=12.0),
    )
    assert isinstance(result, RunOptionsValidationError)
    assert "Invalid seed" in result.message


def test_resolve_run_options_preserves_existing_values_on_empty_input() -> None:
    result = resolve_run_options(
        seed_text="  ",
        date_text=" ",
        current_options=RunOptions(seed=9, date="2025-01-01", timeout_seconds=8.0),
    )
    assert result == RunOptions(seed=9, date="2025-01-01", timeout_seconds=8.0)


def test_build_cli_command_appends_seed_and_date_when_provided() -> None:
    assert build_cli_command(RunOptions(seed=7, date="2025-02-03"))[-4:] == [
        "--seed",
        "7",
        "--date",
        "2025-02-03",
    ]


def test_cli_result_dataclass_fields() -> None:
    result = CliRunResult(status="success", message="ok")
    assert result.status == "success"
    assert result.message == "ok"
