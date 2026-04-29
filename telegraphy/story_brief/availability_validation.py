from __future__ import annotations

from datetime import date
from typing import Any


def parse_availability_boundary(value: Any) -> date:
    if isinstance(value, bool):
        raise ValueError("boundary values must not be booleans")
    if isinstance(value, int):
        return date(value, 1, 1)
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("boundary string values must be ISO dates (YYYY-MM-DD)") from exc
    raise ValueError("boundary values must be an integer year or ISO date string")


def validate_availability_rows(
    section_name: str, key: str, rows: Any
) -> list[tuple[str, date, date]]:
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{section_name}.{key} must be a non-empty list")
    parsed_rows: list[tuple[str, date, date]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError(f"{section_name}.{key}[{idx}] must be [name, start, end]")
        name, start_boundary, end_boundary = row
        if not isinstance(name, str) or not (stripped_name := name.strip()):
            raise ValueError(f"{section_name}.{key}[{idx}][0] must be a non-empty string")
        try:
            start = parse_availability_boundary(start_boundary)
            end = parse_availability_boundary(end_boundary)
        except ValueError as exc:
            raise ValueError(f"{section_name}.{key}[{idx}] {exc}") from exc
        if start > end:
            raise ValueError(f"{section_name}.{key}[{idx}] start must be <= end")
        parsed_rows.append((stripped_name, start, end))

    validate_availability_name_windows(section_name, key, parsed_rows)
    return parsed_rows


def validate_availability_name_windows(
    section_name: str, key: str, rows: list[tuple[str, date, date]]
) -> None:
    windows_by_name: dict[str, list[tuple[date, date, int]]] = {}
    for idx, (name, start, end) in enumerate(rows):
        windows_by_name.setdefault(name.casefold(), []).append((start, end, idx))

    for name_windows in windows_by_name.values():
        name_windows.sort(key=lambda item: item[0])
        for prev, curr in zip(name_windows, name_windows[1:], strict=False):
            _, prev_end, prev_idx = prev
            curr_start, _, curr_idx = curr
            if curr_start <= prev_end:
                raise ValueError(
                    f"{section_name}.{key} has overlapping availability windows "
                    f"for the same name at indices {prev_idx} and {curr_idx}"
                )


def has_date_overlap(
    rows: list[tuple[str, date, date]], range_start: date, range_end: date
) -> bool:
    return any(start <= range_end and end >= range_start for _, start, end in rows)
