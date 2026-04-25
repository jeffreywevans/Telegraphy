from __future__ import annotations

import math
import random
import secrets
from datetime import date, timedelta
from functools import lru_cache
from typing import Any, Iterable, Sequence, TypeVar

if __package__ in (None, ""):
    from _constants import (
        CHARACTER_AVAILABILITY_KEY,
        PARTNER_DISTRIBUTIONS_KEY,
        SETTING_AVAILABILITY_KEY,
    )
    from rendering import render_title
else:
    from ._constants import (
        CHARACTER_AVAILABILITY_KEY,
        PARTNER_DISTRIBUTIONS_KEY,
        SETTING_AVAILABILITY_KEY,
    )
    from .rendering import render_title

PoolValue = TypeVar("PoolValue", str, int)
DEFAULT_SEXUAL_SCENE_TAG_COUNT_WEIGHT_BY_OPTION = {
    2: 0.7,
    3: 0.1,
    4: 0.1,
    5: 0.1,
}

def random_date_in_range(
    rng: random.Random | secrets.SystemRandom, start: date, end: date
) -> date:
    """Return a random date between start and end (inclusive)."""
    day_span = (end - start).days
    return start + timedelta(days=rng.randint(0, day_span))


def stable_sorted_pool(values: Iterable[PoolValue]) -> list[PoolValue]:
    """Return a consistently sorted copy for seed-stable random selection."""
    return sorted(values)


def sorted_pool_from_data(data: dict[str, Any], key: str) -> Sequence[PoolValue]:
    """Read a pre-sorted pool from data when present, else sort lazily."""
    sorted_key = f"{key}_sorted"
    if sorted_key in data:
        return data[sorted_key]
    return stable_sorted_pool(data[key])


def available_characters(selected_date: date, data: dict[str, Any]) -> list[str]:
    """Return characters available for the selected date."""
    return [
        name
        for name, start_date, end_date in data[CHARACTER_AVAILABILITY_KEY]
        if start_date <= selected_date <= end_date
    ]


def available_settings(selected_date: date, data: dict[str, Any]) -> list[str]:
    """Return settings available for the selected date."""
    return [
        setting
        for setting, start_date, end_date in data[SETTING_AVAILABILITY_KEY]
        if start_date <= selected_date <= end_date
    ]


def weighted_choice(
    rng: random.Random | secrets.SystemRandom,
    options: Sequence[str],
    weights: Sequence[float],
) -> str:
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

    for option, weight in zip(options, weights):
        cumulative += weight
        if threshold < cumulative:
            return option

    return options[-1]


@lru_cache(maxsize=16)
def symmetric_peak_weights(length: int) -> tuple[float, ...]:
    """Build symmetric bell-curve-like weights with a center peak."""
    if length <= 0:
        raise ValueError("length must be greater than zero")
    return tuple(float(min(index, length - 1 - index) + 1) for index in range(length))


def pick_story_fields(
    rng: random.Random | secrets.SystemRandom,
    selected_date: date | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, str | int | list[str] | None]:
    """Pick a randomized, schema-compatible story brief field set."""
    if data is None:
        raise ValueError("data must not be None")

    if selected_date is None:
        selected_date = random_date_in_range(rng, data["date_start"], data["date_end"])
    elif not (data["date_start"] <= selected_date <= data["date_end"]):
        raise ValueError(
            f"Date {selected_date.isoformat()} is outside available range "
            f"({data['date_start'].isoformat()} "
            f"to {data['date_end'].isoformat()}). "
            "Try a date within the Commuted archive timeline."
        )
    time_period = selected_date.isoformat()

    characters_for_date = stable_sorted_pool(available_characters(selected_date, data))
    if len(characters_for_date) < 2:
        raise ValueError(
            "Need at least two distinct available characters for year "
            f"{selected_date.year}."
        )

    settings_for_date = stable_sorted_pool(available_settings(selected_date, data))
    if not settings_for_date:
        raise ValueError(
            f"No settings are available for year {selected_date.year}. "
            "Check setting availability data."
        )

    protagonist = rng.choice(characters_for_date)
    eligible_secondary = [name for name in characters_for_date if name != protagonist]
    if not eligible_secondary:
        raise ValueError(
            "Need at least two distinct available characters for year "
            f"{selected_date.year}."
        )
    secondary_character = rng.choice(eligible_secondary)
    setting = rng.choice(settings_for_date)
    title_template = rng.choice(sorted_pool_from_data(data, "titles"))
    sexual_content_level = weighted_choice(
        rng, data["sexual_content_options"], data["sexual_content_weights"]
    )
    sexual_scene_tags: list[str] = []
    if sexual_content_level != "none":
        if "sexual_scene_tag_group_names_sorted" in data:
            tag_group_names = data["sexual_scene_tag_group_names_sorted"]
        else:
            tag_group_names = stable_sorted_pool(data["sexual_scene_tag_groups"])
        configured_tag_count_pairs = list(
            zip(
                data.get(
                    "sexual_scene_tag_count_options",
                    tuple(DEFAULT_SEXUAL_SCENE_TAG_COUNT_WEIGHT_BY_OPTION),
                ),
                data.get(
                    "sexual_scene_tag_count_weights",
                    tuple(DEFAULT_SEXUAL_SCENE_TAG_COUNT_WEIGHT_BY_OPTION.values()),
                ),
            )
        )
        tag_count_options: list[int] = []
        tag_count_weights: list[float] = []
        for count, weight in configured_tag_count_pairs:
            if count <= len(tag_group_names):
                tag_count_options.append(count)
                tag_count_weights.append(weight)
        selected_tag_count = int(
            weighted_choice(
                rng,
                [str(value) for value in tag_count_options],
                tag_count_weights,
            )
        )
        selected_tag_groups = rng.sample(tag_group_names, selected_tag_count)
        tag_groups_sorted = data.get("sexual_scene_tag_groups_sorted", {})
        sexual_scene_tags = [
            rng.choice(
                tag_groups_sorted[group_name]
                if group_name in tag_groups_sorted
                else stable_sorted_pool(data["sexual_scene_tag_groups"][group_name])
            )
            for group_name in selected_tag_groups
        ]

    sexual_partner: str | None = None
    if sexual_content_level != "none":
        for era in data[PARTNER_DISTRIBUTIONS_KEY].get(protagonist, ()):  # pragma: no branch
            if era["date_start"] <= selected_date <= era["date_end"]:
                if era["partners"]:
                    sorted_partner_pairs = stable_sorted_pool(era["partners"])
                    partner_options, partner_weights = map(list, zip(*sorted_partner_pairs))
                    sexual_partner = weighted_choice(rng, partner_options, partner_weights)
                break

    result: dict[str, str | int | list[str] | None] = {
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
    return result
