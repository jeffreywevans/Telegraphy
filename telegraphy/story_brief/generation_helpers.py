from __future__ import annotations

import math
import random
import secrets
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any, TypeAlias, TypeVar, cast

from ._constants import CHARACTER_AVAILABILITY_KEY, SETTING_AVAILABILITY_KEY

RandomSource: TypeAlias = random.Random | secrets.SystemRandom
PoolValue = TypeVar("PoolValue", bound=str | int | tuple[str, float])
OptionT = TypeVar("OptionT")
AvailabilityRows: TypeAlias = Sequence[tuple[str, date, date]]


def stable_sorted_pool(values: Iterable[PoolValue]) -> list[PoolValue]:
    """Return a consistently sorted copy for seed-stable random selection."""
    return sorted(values)


def sorted_pool_from_data(data: Mapping[str, Any], key: str) -> Sequence[PoolValue]:
    """Read a normalized sorted pool, supporting transitional ``*_sorted`` keys."""
    direct_values = data.get(key)
    if direct_values is not None:
        sorted_direct_values = stable_sorted_pool(
            cast(Iterable[PoolValue], direct_values)
        )
        return cast(Sequence[PoolValue], sorted_direct_values)

    sorted_key = f"{key}_sorted"
    fallback_values = data.get(sorted_key)
    if fallback_values is not None:
        return cast(Sequence[PoolValue], fallback_values)

    raise KeyError(f"Missing story-data pool for '{key}' or '{sorted_key}'.")


def _date_in_range(selected_date: date, start_date: date, end_date: date) -> bool:
    """Return whether selected_date falls inside an inclusive date window."""
    return start_date <= selected_date <= end_date


def available_entities(availability_rows: AvailabilityRows, *, selected_date: date) -> list[str]:
    """Return names whose closed availability window contains ``selected_date``."""
    return [
        name
        for name, start_date, end_date in availability_rows
        if _date_in_range(selected_date, start_date, end_date)
    ]


def available_characters(selected_date: date, data: Mapping[str, Any]) -> list[str]:
    """Return characters available for the selected date."""
    return available_entities(
        data[CHARACTER_AVAILABILITY_KEY], selected_date=selected_date
    )


def available_settings(selected_date: date, data: Mapping[str, Any]) -> list[str]:
    """Return settings available for the selected date."""
    return available_entities(data[SETTING_AVAILABILITY_KEY], selected_date=selected_date)


def weighted_choice(
    rng: RandomSource,
    options: Sequence[OptionT],
    weights: Sequence[float],
) -> OptionT:
    """Pick one option using relative weights."""
    if not options:
        raise ValueError("options must not be empty")
    if not weights:
        raise ValueError("weights must not be empty")
    if len(options) != len(weights):
        raise ValueError("options and weights must be the same length")

    for index, weight in enumerate(weights):
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise TypeError(f"weight at index {index} must be a real number")
        if not math.isfinite(weight):
            raise ValueError(f"weight at index {index} must be finite")
        if weight < 0:
            raise ValueError(f"weight at index {index} must be non-negative")

    total = sum(weights)
    if total <= 0:
        raise ValueError("at least one weight must be greater than zero")

    # Avoid random.choices: it consumes RNG differently and breaks seed-stable generation.
    threshold = rng.random() * total
    cumulative = 0.0

    for option, weight in zip(options, weights, strict=True):  # pragma: no branch
        cumulative += weight
        if threshold < cumulative:
            return option

    return options[-1]  # pragma: no cover - floating-point guard for pathological totals.
