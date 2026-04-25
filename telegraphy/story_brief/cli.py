"""CLI entrypoint module for story brief generation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import generate_story_brief as _legacy_cli


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser used by the legacy CLI."""
    parser = argparse.ArgumentParser(
        description="Generate a random story brief Markdown file with YAML front matter."
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=str(_legacy_cli.DEFAULT_OUTPUT_DIR),
        help="Directory where the markdown file will be written.",
    )
    parser.add_argument("--filename", help="Optional explicit filename for the markdown file.")
    parser.add_argument("--seed", type=int, help="Optional random seed for reproducible output.")
    parser.add_argument(
        "--date",
        help="Optional explicit date in YYYY-MM-DD for reproducible scenario testing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the generated markdown to the terminal and do not write a file.",
    )
    parser.add_argument(
        "--validate-strict",
        action="store_true",
        help=(
            "Run strict per-date validation across the configured date range before generating "
            "output."
        ),
    )
    parser.add_argument(
        "--lint-dataset",
        action="store_true",
        help=(
            "Run dataset lint diagnostics (coverage gaps + fragile spots) and exit "
            "without generating output."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the story brief CLI via the legacy implementation."""
    original_argv = sys.argv[:]
    if argv is not None:
        sys.argv = [original_argv[0], *argv]
    try:
        _legacy_cli.main()
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        if code is None:
            return 0
        print(code, file=sys.stderr)
        return 1
    finally:
        sys.argv = original_argv
    return 0


__all__ = ["build_parser", "main"]
