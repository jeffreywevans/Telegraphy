"""Enable `python -m telegraphy.story_brief` execution."""

from typing import NoReturn

from .cli import main


def _run() -> NoReturn:
    """Execute the CLI entrypoint and terminate with its exit code."""
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    _run()
