"""CLI entrypoint module for story brief generation."""

from __future__ import annotations

import argparse
import random
import secrets
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, Union

from . import generate_story_brief as story_brief_cli
from .data_io import DataDirError
from .filenames import (
    DEFAULT_OUTPUT_DIR,
    OutputPathError,
    OutputWriteError,
    resolve_output_path,
    write_output_markdown,
)
from .linting import emit_lint_report, lint_story_data
from .validation import validate_story_data_strict

StoryData = story_brief_cli.StoryData
StoryFields = Mapping[str, Any]
StoryRng = Union[random.Random, secrets.SystemRandom]


def _parse_story_date(raw_date: str) -> date:  # pragma: no cover
    """Parse a YYYY-MM-DD command-line date for argparse."""
    try:
        return date.fromisoformat(raw_date)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--date must be in YYYY-MM-DD format") from exc


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for story brief generation."""
    parser = argparse.ArgumentParser(
        description="Generate a random story brief Markdown file with YAML front matter."
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where the markdown file will be written.",
    )
    parser.add_argument("--filename", help="Optional explicit filename for the markdown file.")
    parser.add_argument("--seed", type=int, help="Optional random seed for reproducible output.")
    parser.add_argument(
        "--date",
        type=_parse_story_date,
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


def _build_rng(seed: int | None) -> StoryRng:
    """Build a random number generator based on an optional deterministic seed."""
    return secrets.SystemRandom() if seed is None else random.Random(seed)


def _print_error(message: str) -> int:
    """Print a user-facing CLI error and return the conventional failure code."""
    print(message, file=sys.stderr)
    return 1


def _write_story_markdown(
    output_dir: str,
    provided_filename: str | None,
    generated_filename: str,
    markdown: str,
    *,
    force: bool,
) -> None:
    """Resolve, create, and write the story brief markdown file."""
    candidate_output_path = resolve_output_path(
        Path(output_dir),
        provided_filename,
        generated_filename,
    )
    candidate_output_path.parent.mkdir(parents=True, exist_ok=True)
    write_output_markdown(candidate_output_path, markdown, force=force)


def _build_generated_filename(fields: StoryFields) -> str:
    """Build the automatic output filename from generated story fields."""
    return story_brief_cli.build_auto_filename(
        str(fields.get("title") or ""),
        today=fields.get("time_period"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the story brief CLI and return an exit code."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        data: StoryData = story_brief_cli.get_data()
    except DataDirError as exc:  # pragma: no cover
        return _print_error(f"Failed to load story brief dataset file. {exc}")
    except ValueError as exc:  # pragma: no cover
        return _print_error(str(exc))

    rng = _build_rng(args.seed)

    if args.lint_dataset:
        report = lint_story_data(data)
        emit_lint_report(report)
        return 1 if report.has_errors else 0

    if args.validate_strict:
        try:
            validate_story_data_strict(data)
        except ValueError as exc:
            return _print_error(str(exc))

    try:
        fields = story_brief_cli.pick_story_fields(rng, selected_date=args.date, data=data)
        markdown = story_brief_cli.to_markdown(fields, data=data)
    except ValueError as exc:
        return _print_error(str(exc))

    if args.print_only:
        print(markdown)
        return 0

    try:
        _write_story_markdown(
            args.output_dir,
            args.filename,
            _build_generated_filename(fields),
            markdown,
            force=args.force,
        )
    except (OutputPathError, OutputWriteError) as exc:
        return _print_error(str(exc))
    except OSError as exc:  # pragma: no cover
        return _print_error(f"Error creating output directory: {exc}")
    print("Generated story brief.")
    return 0


__all__ = ["build_parser", "main"]
