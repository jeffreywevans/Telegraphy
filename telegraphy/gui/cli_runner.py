from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from locale import getpreferredencoding
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
        command.extend(["--date", options.date])
    return command


def decode_output(output: bytes) -> str:
    preferred_encoding = getpreferredencoding(False) or "utf-8"

    try:
        return output.decode(preferred_encoding)
    except UnicodeDecodeError, LookupError:
        return output.decode("utf-8", errors="replace")


def run_story_brief_cli(options: RunOptions) -> CliRunResult:
    try:
        completed = subprocess.run(
            build_cli_command(options),
            check=False,
            capture_output=True,
            text=False,
            timeout=options.timeout_seconds,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return CliRunResult(
            status="error",
            message=f"CLI worker timed out after {options.timeout_seconds:g}s.",
        )
    except OSError as exc:
        return CliRunResult(status="error", message=f"Could not run Telegraphy CLI:\n{exc}")

    stdout = decode_output(completed.stdout)
    stderr = decode_output(completed.stderr)

    if completed.returncode == 0:
        return CliRunResult(status="success", message=stdout.strip())

    message = stderr.strip() or stdout.strip() or UNKNOWN_FAILURE_MESSAGE
    return CliRunResult(status="error", message=message)
