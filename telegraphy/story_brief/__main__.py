"""Run ``telegraphy.story_brief`` as a module."""

from __future__ import annotations

from typing import NoReturn

from .cli import main


def _run() -> NoReturn:
    """Execute the CLI and exit the interpreter with its return code."""
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    _run()
