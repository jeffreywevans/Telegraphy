"""CLI entrypoint module for story brief generation."""

from __future__ import annotations

import argparse
import random
import secrets
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

if __package__ in (None, ""):
    import generate_story_brief as _legacy_cli
    from filenames import (
        DEFAULT_OUTPUT_DIR,
        OutputPathError,
        OutputWriteError,
        resolve_output_path,
        write_output_markdown,
    )
else:
    from . import generate_story_brief as _legacy_cli
    from .filenames import (
        DEFAULT_OUTPUT_DIR,
        OutputPathError,
        OutputWriteError,
        resolve_output_path,
        write_output_markdown,
    )
    from .linting import emit_lint_report, lint_story_data
    from .validation import validate_story_data_strict

if __package__ in (None, ""):
    from linting import emit_lint_report, lint_story_data
    from validation import validate_story_data_strict


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
    """Run the story brief CLI and return an exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 0 if exc.code is None else 1

    try:
        data = _legacy_cli._get_data_cached() if args.lint_dataset else _legacy_cli.get_data()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    rng: random.Random | secrets.SystemRandom
    if args.seed is None:
        rng = secrets.SystemRandom()
    else:
        rng = random.Random(args.seed)

    if args.lint_dataset:
        report = lint_story_data(data)
        emit_lint_report(report)
        return 1 if report.has_errors else 0

    if args.validate_strict:
        try:
            validate_story_data_strict(data)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    selected_date: date | None = None
    if args.date:
        try:
            selected_date = date.fromisoformat(args.date)
        except ValueError:
            print("--date must be in YYYY-MM-DD format", file=sys.stderr)
            return 1

    try:
        fields = _legacy_cli.pick_story_fields(rng, selected_date=selected_date, data=data)
        markdown = _legacy_cli.to_markdown(fields, data=data)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.print_only:
        print(markdown)
        return 0

    generated_filename = _legacy_cli.build_auto_filename(
        str(fields["title"]),
        today=str(fields.get("time_period", date.today().isoformat())),
    )
    try:
        candidate_output_path = resolve_output_path(
            Path(args.output_dir),
            args.filename,
            generated_filename,
        )
        candidate_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_output_markdown(candidate_output_path, markdown, force=args.force)
    except OutputPathError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OutputWriteError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error creating output directory: {exc}", file=sys.stderr)
        return 1
    print("Generated story brief.")
    return 0


__all__ = ["build_parser", "main"]
