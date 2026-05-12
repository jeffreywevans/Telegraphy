from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from ._constants import PARTNER_DISTRIBUTIONS_KEY
from .linting import _collect_interval_lint_ranges, build_coverage_checkpoints


def validate_story_data_strict(data: Mapping[str, Any]) -> None:
    """Validate per-date generation preconditions across the configured date range."""
    range_start = data["date_start"]
    range_end = data["date_end"]
    lint_data: Mapping[str, Any] = (
        data
        if PARTNER_DISTRIBUTIONS_KEY in data
        else {**data, PARTNER_DISTRIBUTIONS_KEY: {}}
    )

    sorted_checkpoints = build_coverage_checkpoints(
        lint_data,
        range_start=range_start,
        range_end=range_end,
    )
    interval_results = _collect_interval_lint_ranges(
        lint_data,
        sorted_checkpoints=sorted_checkpoints,
        range_end=range_end,
    )

    earliest_character_gap = _earliest_gap_date(interval_results.missing_character_ranges)
    earliest_setting_gap = _earliest_gap_date(interval_results.missing_setting_ranges)

    if earliest_character_gap is not None and (
        earliest_setting_gap is None or earliest_character_gap <= earliest_setting_gap
    ):
        raise ValueError(
            "Strict validation failed: fewer than two distinct available characters on "
            f"{earliest_character_gap.isoformat()}."
        )

    if earliest_setting_gap is not None:
        raise ValueError(
            "Strict validation failed: no available settings on "
            f"{earliest_setting_gap.isoformat()}."
        )


def _earliest_gap_date(gap_ranges: list[tuple[date, date]]) -> date | None:
    """Return the earliest date represented by one or more closed date ranges."""
    return min((start for start, _ in gap_ranges), default=None)
