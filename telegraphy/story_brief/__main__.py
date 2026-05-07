"""Run ``telegraphy.story_brief`` as a module."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":  # pragma: no cover
    # Use sys.exit to normalize supported return types from `main`
    # (`None`, `int`, or `str`) and avoid an extra wrapper function.
    sys.exit(main())
