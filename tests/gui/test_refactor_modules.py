from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from telegraphy.gui import cli_runner
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
    assert build_cli_command(RunOptions(seed=7, date="2025-02-03"))[-3:] == [
        "--seed",
        "7",
        "--date=2025-02-03",
    ]


def test_cli_result_dataclass_fields() -> None:
    result = CliRunResult(status="success", message="ok")
    assert result.status == "success"
    assert result.message == "ok"


def test_run_story_brief_cli_uses_explicit_utf8_io(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        observed["command"] = command
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=" café ", stderr="")

    monkeypatch.setenv("PYTHONIOENCODING", "latin-1")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = cli_runner.run_story_brief_cli(
        RunOptions(seed=1, date="2025-01-01", timeout_seconds=3)
    )
    assert result == CliRunResult(status="success", message="café")
    assert observed["text"] is True
    assert observed["encoding"] == "utf-8"
    assert observed["errors"] == "replace"
    child_environment = observed["env"]
    assert isinstance(child_environment, dict)
    assert child_environment["PYTHONIOENCODING"] == "utf-8"


def test_run_story_brief_cli_uses_stderr_then_stdout_then_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=9, stdout=" out ", stderr=" err "),
    )
    assert cli_runner.run_story_brief_cli(RunOptions()).message == "err"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=9, stdout=" out ", stderr=" "),
    )
    assert cli_runner.run_story_brief_cli(RunOptions()).message == "out"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=9, stdout=" ", stderr=" "),
    )
    assert (
        cli_runner.run_story_brief_cli(RunOptions()).message == cli_runner.UNKNOWN_FAILURE_MESSAGE
    )


def test_run_story_brief_cli_handles_timeout_and_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_timeout(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd=["telegraphy"], timeout=5.0)

    monkeypatch.setattr(subprocess, "run", raise_timeout)
    timeout_result = cli_runner.run_story_brief_cli(RunOptions(timeout_seconds=5.0))
    assert timeout_result.status == "error"
    assert timeout_result.message == "CLI worker timed out after 5s."

    def raise_oserror(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise OSError("noexec")

    monkeypatch.setattr(subprocess, "run", raise_oserror)
    os_error_result = cli_runner.run_story_brief_cli(RunOptions())
    assert os_error_result.status == "error"
    assert "Could not run Telegraphy CLI" in os_error_result.message
