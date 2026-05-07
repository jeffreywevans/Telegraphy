"""Run ``telegraphy.story_brief`` as a module."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":  # pragma: no cover
    # Use sys.exit to ensure the exit code from `main` is passed to the shell
    # and avoid an extra wrapper function.
    sys.exit(main())
