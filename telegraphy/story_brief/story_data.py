from __future__ import annotations

from datetime import date
from typing import TypedDict


class NormalizedPartnerEra(TypedDict):
    date_start: date
    date_end: date
    partners: tuple[tuple[str, float], ...]


class StoryData(TypedDict):
    titles: tuple[str, ...]
    titles_sorted: tuple[str, ...]
    character_availability: tuple[tuple[str, date, date], ...]
    setting_availability: tuple[tuple[str, date, date], ...]
    central_conflicts: tuple[str, ...]
    inciting_pressures: tuple[str, ...]
    ending_types: tuple[str, ...]
    style_guidance: tuple[str, ...]
    weather_comment: str
    weather: tuple[str, ...]
    central_conflicts_sorted: tuple[str, ...]
    inciting_pressures_sorted: tuple[str, ...]
    ending_types_sorted: tuple[str, ...]
    style_guidance_sorted: tuple[str, ...]
    weather_sorted: tuple[str, ...]
    date_start: date
    date_end: date
    sexual_content_presence_options: tuple[str, ...]
    sexual_content_presence_weights: tuple[float, ...]
    sexual_scene_tag_groups: dict[str, tuple[str, ...]]
    sexual_scene_tag_group_names_sorted: tuple[str, ...]
    sexual_scene_tag_groups_sorted: dict[str, tuple[str, ...]]
    sexual_scene_tag_count_weights_by_presence: dict[str, dict[int, float]]
    sexual_scene_required_tag_groups_by_presence: dict[str, tuple[str, ...]]
    sexual_scene_optional_tag_groups: tuple[str, ...]
    word_count_targets: tuple[int, ...]
    word_count_targets_sorted: tuple[int, ...]
    ordered_keys: tuple[str, ...]
    writing_preamble: str
    dataset_version: str
    partner_distributions: dict[str, tuple[NormalizedPartnerEra, ...]]
