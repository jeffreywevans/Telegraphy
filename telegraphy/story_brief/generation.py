from __future__ import annotations

import math
import random
import secrets
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
from functools import lru_cache
from typing import Any, TypeAlias, TypeVar, cast

from ._constants import (
    CHARACTER_AVAILABILITY_KEY,
    PARTNER_DISTRIBUTIONS_KEY,
    SETTING_AVAILABILITY_KEY,
)
from .rendering import render_title

RandomSource: TypeAlias = random.Random | secrets.SystemRandom
GeneratedFieldValue: TypeAlias = str | int | list[str] | None
GeneratedFields: TypeAlias = dict[str, GeneratedFieldValue]
PoolValue = TypeVar("PoolValue", bound=str | int | tuple[str, float])
OptionT = TypeVar("OptionT")

DEFAULT_SEXUAL_SCENE_TAG_COUNT_WEIGHT_BY_OPTION: dict[int, float] = {
    2: 0.7,
    3: 0.1,
    4: 0.1,
    5: 0.1,
}


def random_date_in_range(rng: RandomSource, start: date, end: date) -> date:
    """Return a random date between start and end, inclusive."""
    day_span = (end - start).days
    return start + timedelta(days=rng.randint(0, day_span))


def stable_sorted_pool(values: Iterable[PoolValue]) -> list[PoolValue]:
    """Return a consistently sorted copy for seed-stable random selection."""
    return sorted(values)


def sorted_pool_from_data(data: Mapping[str, Any], key: str) -> Sequence[PoolValue]:
    """Read a pre-sorted pool from data when present, otherwise sort lazily.

    Normalized production data provides ``<key>_sorted`` entries so generation
    remains deterministic even if raw dataset order changes. The lazy fallback
    is retained for lightweight callers and compatibility tests that pass only
    the raw pool.
    """
    sorted_key = f"{key}_sorted"
    try:
        return cast(Sequence[PoolValue], data[sorted_key])
    except KeyError:  # pragma: no cover - compatibility fallback for minimal data maps.
        return stable_sorted_pool(cast(Iterable[PoolValue], data[key]))


def _date_in_range(selected_date: date, start_date: date, end_date: date) -> bool:
    """Return whether selected_date falls inside an inclusive date window."""
    return start_date <= selected_date <= end_date


def available_characters(selected_date: date, data: Mapping[str, Any]) -> list[str]:
    """Return characters available for the selected date."""
    return [
        name
        for name, start_date, end_date in data[CHARACTER_AVAILABILITY_KEY]
        if _date_in_range(selected_date, start_date, end_date)
    ]


def available_settings(selected_date: date, data: Mapping[str, Any]) -> list[str]:
    """Return settings available for the selected date."""
    return [
        setting
        for setting, start_date, end_date in data[SETTING_AVAILABILITY_KEY]
        if _date_in_range(selected_date, start_date, end_date)
    ]


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


@lru_cache(maxsize=16)
def symmetric_peak_weights(length: int) -> tuple[float, ...]:
    """Build symmetric bell-curve-like weights with a center peak."""
    if length <= 0:
        raise ValueError("length must be greater than zero")
    return tuple(float(min(index, length - 1 - index) + 1) for index in range(length))


def pick_story_fields(
    rng: RandomSource,
    selected_date: date | None = None,
    data: Mapping[str, Any] | None = None,
) -> GeneratedFields:
    """Pick a randomized, schema-compatible story brief field set."""
    if data is None:  # pragma: no cover - facade resolves production data before calling.
        raise ValueError("data must not be None")

    selected_date = resolve_selected_date(rng, selected_date, data)
    time_period = selected_date.isoformat()
    protagonist, secondary_character = pick_story_characters(rng, selected_date, data)
    setting = pick_story_setting(rng, selected_date, data)

    title_template: str = rng.choice(
        cast(Sequence[str], sorted_pool_from_data(data, "titles"))
    )
    sexual_content_level = weighted_choice(
        rng, data["sexual_content_options"], data["sexual_content_weights"]
    )
    sexual_scene_tags = pick_sexual_scene_tags(rng, sexual_content_level, data)
    sexual_partner = pick_sexual_partner(
        rng, sexual_content_level, data, protagonist, selected_date
    )

    return {
        "title": render_title(
            title_template,
            protagonist=protagonist,
            setting=setting,
            time_period=time_period,
        ),
        "protagonist": protagonist,
        "secondary_character": secondary_character,
        "time_period": time_period,
        "setting": setting,
        "weather": weighted_choice(
            rng,
            data["weather"],
            symmetric_peak_weights(len(data["weather"])),
        ),
        "central_conflict": rng.choice(sorted_pool_from_data(data, "central_conflicts")),
        "inciting_pressure": rng.choice(sorted_pool_from_data(data, "inciting_pressures")),
        "ending_type": rng.choice(sorted_pool_from_data(data, "ending_types")),
        "style_guidance": rng.choice(sorted_pool_from_data(data, "style_guidance")),
        "sexual_content_level": sexual_content_level,
        "sexual_partner": sexual_partner,
        "sexual_scene_tags": sexual_scene_tags,
        "word_count_target": rng.choice(sorted_pool_from_data(data, "word_count_targets")),
    }


def pick_story_characters(
    rng: RandomSource,
    selected_date: date,
    data: Mapping[str, Any],
) -> tuple[str, str]:
    """Pick protagonist and secondary character for a date."""
    characters_for_date = stable_sorted_pool(available_characters(selected_date, data))
    distinct_characters_for_date = list(dict.fromkeys(characters_for_date))
    if len(distinct_characters_for_date) < 2:
        raise ValueError(
            "Need at least two distinct available characters for year "
            f"{selected_date.year}."
        )

    protagonist, secondary_character = rng.sample(distinct_characters_for_date, 2)
    return protagonist, secondary_character


def pick_story_setting(
    rng: RandomSource,
    selected_date: date,
    data: Mapping[str, Any],
) -> str:
    """Pick an available setting for a date."""
    settings_for_date = stable_sorted_pool(available_settings(selected_date, data))
    try:
        return rng.choice(settings_for_date)
    except IndexError as exc:  # pragma: no cover - dataset validation normally prevents this.
        raise ValueError(
            f"No settings are available for year {selected_date.year}. "
            "Check setting availability data."
        ) from exc


def resolve_selected_date(
    rng: RandomSource,
    selected_date: date | None,
    data: Mapping[str, Any],
) -> date:
    """Resolve and validate story date selection."""
    if selected_date is None:
        return random_date_in_range(rng, data["date_start"], data["date_end"])
    if _date_in_range(selected_date, data["date_start"], data["date_end"]):
        return selected_date
    raise ValueError(
        f"Date {selected_date.isoformat()} is outside available range "
        f"({data['date_start'].isoformat()} "
        f"to {data['date_end'].isoformat()}). "
        "Try a date within the Commuted archive timeline."
    )


def pick_sexual_scene_tags(
    rng: RandomSource,
    sexual_content_level: str,
    data: Mapping[str, Any],
) -> list[str]:
    """Pick sexual scene tags when sexual content is enabled."""
    if sexual_content_level == "none":
        return []

    tag_group_names = _sexual_scene_tag_group_names(data)
    tag_count_options, tag_count_weights = build_sexual_scene_tag_count_distribution(
        tag_group_names, data
    )
    selected_tag_count = weighted_choice(
        rng,
        tag_count_options,
        tag_count_weights,
    )
    selected_tag_groups = rng.sample(tag_group_names, selected_tag_count)
    return pick_tags_from_selected_groups(rng, selected_tag_groups, data)


def _sexual_scene_tag_group_names(data: Mapping[str, Any]) -> Sequence[str]:
    """Return deterministic sexual-scene tag group names."""
    try:
        return cast(Sequence[str], data["sexual_scene_tag_group_names_sorted"])
    except KeyError:  # pragma: no cover - compatibility fallback for minimal data maps.
        return stable_sorted_pool(cast(Iterable[str], data["sexual_scene_tag_groups"]))


def build_sexual_scene_tag_count_distribution(
    tag_group_names: Sequence[str], data: Mapping[str, Any]
) -> tuple[list[int], list[float]]:
    """Build valid sexual scene tag count options and weights."""
    options = cast(
        Sequence[int],
        data.get(
            "sexual_scene_tag_count_options",
            tuple(DEFAULT_SEXUAL_SCENE_TAG_COUNT_WEIGHT_BY_OPTION),
        ),
    )
    raw_weights = data.get("sexual_scene_tag_count_weights")
    weights: Sequence[float]
    if isinstance(raw_weights, Mapping) and raw_weights:
        weights = [float(raw_weights.get(str(option)) or 0.0) for option in options]
    else:
        weights = cast(
            Sequence[float],
            raw_weights or tuple(DEFAULT_SEXUAL_SCENE_TAG_COUNT_WEIGHT_BY_OPTION.values()),
        )
    configured_tag_count_pairs = zip(options, weights, strict=False)

    tag_count_options: list[int] = []
    tag_count_weights: list[float] = []
    for count, weight in configured_tag_count_pairs:
        if count <= len(tag_group_names):
            tag_count_options.append(count)
            tag_count_weights.append(weight)

    if not tag_count_options:
        max_supported_count = len(tag_group_names)
        raise ValueError(
            "No valid sexual scene tag count options remain after filtering "
            "configured counts against available sexual scene tag groups "
            f"(max supported count: {max_supported_count})"
        )

    return tag_count_options, tag_count_weights


def pick_tags_from_selected_groups(
    rng: RandomSource,
    selected_tag_groups: Sequence[str],
    data: Mapping[str, Any],
) -> list[str]:
    """Pick one random tag from each selected tag group."""
    return [
        rng.choice(_sorted_tags_for_group(group_name, data))
        for group_name in selected_tag_groups
    ]


def _sorted_tags_for_group(group_name: str, data: Mapping[str, Any]) -> Sequence[str]:
    """Return deterministic tags for one sexual-scene tag group."""
    tag_groups_sorted = cast(
        Mapping[str, Sequence[str]], data.get("sexual_scene_tag_groups_sorted", {})
    )
    try:
        return tag_groups_sorted[group_name]
    except KeyError:  # pragma: no cover - compatibility fallback for minimal data maps.
        tag_groups = cast(Mapping[str, Iterable[str]], data["sexual_scene_tag_groups"])
        return stable_sorted_pool(tag_groups[group_name])


def pick_sexual_partner(
    rng: RandomSource,
    sexual_content_level: str,
    data: Mapping[str, Any],
    protagonist: str,
    selected_date: date,
) -> str | None:
    """Pick partner for sexual content, if available for selected era."""
    if sexual_content_level == "none":
        return None
    for era in data[PARTNER_DISTRIBUTIONS_KEY].get(protagonist, ()):
        if _date_in_range(selected_date, era["date_start"], era["date_end"]):
            return weighted_partner_for_era(rng, era["partners"])
    return None


def weighted_partner_for_era(
    rng: RandomSource,
    partners: Sequence[tuple[str, float]],
) -> str | None:
    """Select a weighted partner for a matched era."""
    if not partners:  # pragma: no cover - valid partner eras either contain weights or are absent.
        return None
    sorted_partner_pairs = stable_sorted_pool(partners)
    partner_options: list[str] = [partner_name for partner_name, _ in sorted_partner_pairs]
    partner_weights: list[float] = [partner_weight for _, partner_weight in sorted_partner_pairs]
    return weighted_choice(rng, partner_options, partner_weights)
