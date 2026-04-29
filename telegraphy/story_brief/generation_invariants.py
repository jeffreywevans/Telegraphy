from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from ._constants import CHARACTER_AVAILABILITY_KEY, SETTING_AVAILABILITY_KEY
from ._range_utils import add_clipped_range_checkpoints


def validate_story_data_strict(data: Mapping[str, Any]) -> None:
    """Validate per-date generation preconditions across the configured date range."""
    range_start = data["date_start"]
    range_end = data["date_end"]
    checkpoints: set[date] = {range_start, range_end}
    for source in (data[CHARACTER_AVAILABILITY_KEY], data[SETTING_AVAILABILITY_KEY]):
        add_clipped_range_checkpoints(
            checkpoints=checkpoints,
            ranges=[(row_start, row_end) for _, row_start, row_end in source],
            range_start=range_start,
            range_end=range_end,
        )
    for selected_date in sorted(checkpoints):
        characters = [
            name
            for name, start_date, end_date_for_row in data[CHARACTER_AVAILABILITY_KEY]
            if start_date <= selected_date <= end_date_for_row
        ]
        if len(characters) < 2:
            raise ValueError(
                "Strict validation failed: fewer than two distinct available characters on "
                f"{selected_date.isoformat()}."
            )

        if not any(
            start_date <= selected_date <= end_date_for_row
            for _, start_date, end_date_for_row in data[SETTING_AVAILABILITY_KEY]
        ):
            raise ValueError(
                "Strict validation failed: no available settings on "
                f"{selected_date.isoformat()}."
            )
