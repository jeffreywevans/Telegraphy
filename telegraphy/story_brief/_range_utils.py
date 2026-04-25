from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta


def add_clipped_range_checkpoints(
    *,
    checkpoints: set[date],
    ranges: Iterable[tuple[date, date]],
    range_start: date,
    range_end: date,
) -> None:
    one_day = timedelta(days=1)
    for row_start, row_end in ranges:
        clipped_start = max(range_start, row_start)
        clipped_end = min(range_end, row_end)
        if clipped_start <= clipped_end:
            checkpoints.add(clipped_start)
            if clipped_end < range_end:
                checkpoints.add(clipped_end + one_day)
