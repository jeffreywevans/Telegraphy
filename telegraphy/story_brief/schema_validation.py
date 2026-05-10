from __future__ import annotations

from datetime import date
from typing import Any, NamedTuple

from ._constants import CHARACTER_AVAILABILITY_KEY, SETTING_AVAILABILITY_KEY
from .availability_validation import validate_availability_rows
from .partner_models import PartnerDistributionDataset, require_keys
from .schema_validation_config import (
    CONFIG_REQUIRED_KEYS,
    normalize_config,
    parse_and_validate_config_dates,
    validate_config_date_overlap,
    validate_config_versions,
    validate_ordered_keys,
    validate_partner_distributions,
    validate_sexual_content_weights,
    validate_sexual_scene_tag_count_weights_by_presence,
    validate_sexual_scene_tag_group_presence_rules,
    validate_sexual_scene_tag_groups,
    validate_word_count_targets,
    validate_writing_preamble,
)
from .schema_validation_titles_prompts import (
    validate_prompt_lists,
    validate_titles,
)

ENTITY_AVAILABILITY_KEYS = frozenset({CHARACTER_AVAILABILITY_KEY, SETTING_AVAILABILITY_KEY})


class ValidatedStoryData(NamedTuple):
    character_availability: list[tuple[str, date, date]]
    setting_availability: list[tuple[str, date, date]]
    date_start: date
    date_end: date
    normalized_config: dict[str, Any]
    partner_distributions: PartnerDistributionDataset


def _validate_entities(
    entities: dict[str, Any],
) -> tuple[list[tuple[str, date, date]], list[tuple[str, date, date]]]:
    require_keys("entities", entities, ENTITY_AVAILABILITY_KEYS)
    character_rows = validate_availability_rows(
        "entities", CHARACTER_AVAILABILITY_KEY, entities[CHARACTER_AVAILABILITY_KEY]
    )
    setting_rows = validate_availability_rows(
        "entities", SETTING_AVAILABILITY_KEY, entities[SETTING_AVAILABILITY_KEY]
    )
    return character_rows, setting_rows


def validate_story_data(
    titles: dict[str, Any],
    entities: dict[str, Any],
    prompts: dict[str, Any],
    config: dict[str, Any],
    partner_distributions: dict[str, Any],
) -> ValidatedStoryData:
    """Validate raw dataset payloads and return normalized availability metadata."""
    validate_titles(titles)
    character_rows, setting_rows = _validate_entities(entities)

    validate_prompt_lists(prompts)
    normalized_config = normalize_config(config)

    require_keys("config", normalized_config, CONFIG_REQUIRED_KEYS)
    validate_config_versions(normalized_config)
    start, end = parse_and_validate_config_dates(normalized_config)
    validate_config_date_overlap(
        character_rows,
        setting_rows,
        start,
        end,
        CHARACTER_AVAILABILITY_KEY,
        SETTING_AVAILABILITY_KEY,
    )
    validate_sexual_content_weights(normalized_config)
    validate_sexual_scene_tag_groups(normalized_config)
    validate_sexual_scene_tag_count_weights_by_presence(normalized_config)
    validate_sexual_scene_tag_group_presence_rules(normalized_config)
    validate_word_count_targets(normalized_config)
    validate_ordered_keys(normalized_config)
    validate_writing_preamble(normalized_config)
    partner_distribution_index = validate_partner_distributions(
        partner_distributions,
        config_start=start,
        config_end=end,
        character_rows=character_rows,
    )

    return ValidatedStoryData(
        character_availability=character_rows,
        setting_availability=setting_rows,
        date_start=start,
        date_end=end,
        normalized_config=normalized_config,
        partner_distributions=partner_distribution_index,
    )
