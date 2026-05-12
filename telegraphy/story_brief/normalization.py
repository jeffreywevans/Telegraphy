from __future__ import annotations

from typing import Any

from ._constants import PROMPT_LIST_KEYS
from .generation_helpers import stable_sorted_pool
from .schema_validation import validate_story_data


def _build_story_data(dataset_payloads: dict[str, Any]) -> dict[str, Any]:
    """Normalize validated story dataset payloads into runtime selection structures."""
    titles = dataset_payloads["titles"]
    entities = dataset_payloads["entities"]
    prompts = dataset_payloads["prompts"]
    weather = dataset_payloads["weather"]
    config = dataset_payloads["config"]
    partner_distributions = dataset_payloads["partner_distributions"]

    validated = validate_story_data(
        titles,
        entities,
        prompts,
        weather,
        config,
        partner_distributions,
    )
    normalized_config = validated.normalized_config

    normalized_titles = tuple(stable_sorted_pool(str(value) for value in titles["titles"]))
    prompt_lists = {
        key: tuple(stable_sorted_pool(str(value) for value in prompts[key]))
        for key in PROMPT_LIST_KEYS
    }

    sexual_scene_tag_groups = {
        str(group_name): tuple(stable_sorted_pool(str(tag) for tag in tags))
        for group_name, tags in normalized_config["sexual_scene_tag_groups"].items()
    }
    sexual_scene_tag_count_weights_by_presence = {
        str(presence): {
            int(option_raw): float(weight_raw)
            for option_raw, weight_raw in sorted(weights.items(), key=lambda item: int(item[0]))
        }
        for presence, weights in normalized_config[
            "sexual_scene_tag_count_weights_by_presence"
        ].items()
    }
    sexual_content_presence_options = tuple(
        str(v) for v in normalized_config["sexual_content_presence_options"]
    )
    word_count_targets = tuple(
        stable_sorted_pool(int(value) for value in normalized_config["word_count_targets"])
    )

    return {
        "titles": normalized_titles,
        "character_availability": tuple(validated.character_availability),
        "setting_availability": tuple(validated.setting_availability),
        **prompt_lists,
        "weather_comment": str(weather.get("weather_comment", "")),
        "weather": tuple(stable_sorted_pool(str(value) for value in weather["weather"])),
        "date_start": validated.date_start,
        "date_end": validated.date_end,
        "sexual_content_presence_options": sexual_content_presence_options,
        "sexual_content_presence_weights": tuple(
            float(v) for v in normalized_config["sexual_content_presence_weights"]
        ),
        "sexual_scene_tag_groups": sexual_scene_tag_groups,
        "sexual_scene_tag_group_names": tuple(stable_sorted_pool(sexual_scene_tag_groups)),
        "sexual_scene_tag_count_weights_by_presence": sexual_scene_tag_count_weights_by_presence,
        "sexual_scene_required_tag_groups_by_presence": {
            str(presence): tuple(str(group_name) for group_name in groups)
            for presence, groups in normalized_config[
                "sexual_scene_required_tag_groups_by_presence"
            ].items()
        },
        "sexual_scene_optional_tag_groups": tuple(
            str(group_name) for group_name in normalized_config["sexual_scene_optional_tag_groups"]
        ),
        "word_count_targets": word_count_targets,
        "ordered_keys": tuple(str(v) for v in normalized_config["ordered_keys"]),
        "writing_preamble": str(normalized_config["writing_preamble"]),
        "dataset_version": str(normalized_config["dataset_version"]),
        "partner_distributions": {
            protagonist: tuple(
                {
                    "date_start": era.date_start,
                    "date_end": era.date_end,
                    "partners": tuple((entry.partner, entry.weight) for entry in era.partners),
                }
                for era in distribution.eras
            )
            for protagonist, distribution in validated.partner_distributions.by_character.items()
        },
    }
