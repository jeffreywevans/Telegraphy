from __future__ import annotations

from typing import Any


def validate_string_list(section_name: str, key: str, values: Any) -> None:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{section_name}.{key} must be a non-empty list")
    for idx, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{section_name}.{key}[{idx}] must be a non-empty string")


def validate_no_duplicate_strings(section_name: str, key: str, values: list[str]) -> None:
    seen: dict[str, int] = {}
    for idx, value in enumerate(values):
        normalized = value.strip().casefold()
        if normalized in seen:
            first_idx = seen[normalized]
            raise ValueError(
                f"{section_name}.{key} contains duplicate value at index {idx} "
                f"(first seen at index {first_idx})"
            )
        seen[normalized] = idx
