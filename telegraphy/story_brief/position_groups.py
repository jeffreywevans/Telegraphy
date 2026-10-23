"""Validate and normalize weighted position families."""

from __future__ import annotations

import math
from typing import TypedDict


class PositionGroup(TypedDict):
    """A percentage weight and an equally likely pool of position variants."""

    weight: float
    variants: tuple[str, ...]


def normalize_position_groups(raw: object) -> dict[str, PositionGroup]:
    """Return sorted families whose percentage weights total 100."""
    if not isinstance(raw, dict) or not raw:
        raise ValueError("position groups must be a non-empty object")
    result: dict[str, PositionGroup] = {}
    for name, entry in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("position group names must be non-empty strings")
        result[name] = _normalize_position_group(name, entry)
    if not math.isclose(sum(group["weight"] for group in result.values()), 100, abs_tol=1e-9):
        raise ValueError("position group weights must total 100 percent")
    return dict(sorted(result.items()))


def _normalize_position_group(name: str, entry: object) -> PositionGroup:
    """Validate one family's weight and variants, preserving diagnostic messages."""
    if not isinstance(entry, dict) or set(entry) != {"weight", "variants"}:
        raise ValueError(f"position group {name}: expected weight and variants")
    weight = entry["weight"]
    if (
        isinstance(weight, bool)
        or not isinstance(weight, (int, float))
        or not math.isfinite(weight)
        or not 1 <= weight <= 32
    ):
        raise ValueError(f"position group {name}: weight must be between 1 and 32 percent")
    variants = entry["variants"]
    if (
        not isinstance(variants, list)
        or not variants
        or any(not isinstance(tag, str) or not tag.strip() for tag in variants)
    ):
        raise ValueError(f"position group {name}: variants must be a non-empty string list")
    if len(set(variants)) != len(variants):
        raise ValueError(f"position group {name}: duplicate variants")
    return {"weight": float(weight), "variants": tuple(sorted(variants))}
