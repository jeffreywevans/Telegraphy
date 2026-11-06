from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Final

from .models import RunOptions

UNKNOWN_FAILURE_MESSAGE: Final[str] = "Unknown CLI failure."


@dataclass(frozen=True)
class CliRunResult:
    status: str
    message: str


def build_cli_command(options: RunOptions) -> list[str]:
    command = [sys.executable, "-m", "telegraphy.story_brief", "--print-only"]
    if options.seed is not None:
        command.extend(["--seed", str(options.seed)])
    if options.date:
        command.append(f"--date={options.date}")
    return command


def run_story_brief_cli(options: RunOptions) -> CliRunResult:
    child_environment = os.environ.copy()
    child_environment["PYTHONIOENCODING"] = "utf-8"
    try:
        completed = subprocess.run(
            build_cli_command(options),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=options.timeout_seconds,
            env=child_environment,
        )
    except subprocess.TimeoutExpired:
        return CliRunResult(
            status="error",
            message=f"CLI worker timed out after {options.timeout_seconds:g}s.",
        )
    except OSError as exc:
        return CliRunResult(status="error", message=f"Could not run Telegraphy CLI:\n{exc}")

    stdout = completed.stdout
    stderr = completed.stderr

    if completed.returncode == 0:
        return CliRunResult(status="success", message=stdout.strip())

    message = stderr.strip() or stdout.strip() or UNKNOWN_FAILURE_MESSAGE
    return CliRunResult(status="error", message=message)
