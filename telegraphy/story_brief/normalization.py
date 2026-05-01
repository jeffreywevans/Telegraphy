from __future__ import annotations

from typing import Any

from ._constants import PROMPT_LIST_KEYS
from .generation import stable_sorted_pool
from .validation import validate_story_data


def _build_story_data(dataset_payloads: dict[str, Any]) -> dict[str, Any]:
    """Normalize validated story dataset payloads into runtime selection structures."""
    titles = dataset_payloads["titles"]
    entities = dataset_payloads["entities"]
    prompts = dataset_payloads["prompts"]
    config = dataset_payloads["config"]
    partner_distributions = dataset_payloads["partner_distributions"]

    validated = validate_story_data(titles, entities, prompts, config, partner_distributions)
    prompt_lists = {key: tuple(str(value) for value in prompts[key]) for key in PROMPT_LIST_KEYS}

    sexual_scene_tag_groups = {
        str(group_name): tuple(str(tag) for tag in tags)
        for group_name, tags in config["sexual_scene_tag_groups"].items()
    }
    sorted_items = sorted(
        config["sexual_scene_tag_count_weights"].items(),
        key=lambda item: int(item[0]),
    )
    if sorted_items:
        options_str, weights_raw = zip(*sorted_items, strict=False)
    else:
        options_str, weights_raw = (), ()
    sexual_scene_tag_count_options = tuple(map(int, options_str))
    sexual_scene_tag_count_weights = tuple(map(float, weights_raw))

    return {
        "titles": tuple(str(v) for v in titles["titles"]),
        "titles_sorted": tuple(stable_sorted_pool(str(v) for v in titles["titles"])),
        "character_availability": tuple(validated.character_availability),
        "setting_availability": tuple(validated.setting_availability),
        "central_conflicts": prompt_lists["central_conflicts"],
        "inciting_pressures": prompt_lists["inciting_pressures"],
        "ending_types": prompt_lists["ending_types"],
        "style_guidance": prompt_lists["style_guidance"],
        "weather": prompt_lists["weather"],
        "central_conflicts_sorted": tuple(stable_sorted_pool(prompt_lists["central_conflicts"])),
        "inciting_pressures_sorted": tuple(stable_sorted_pool(prompt_lists["inciting_pressures"])),
        "ending_types_sorted": tuple(stable_sorted_pool(prompt_lists["ending_types"])),
        "style_guidance_sorted": tuple(stable_sorted_pool(prompt_lists["style_guidance"])),
        "weather_sorted": tuple(stable_sorted_pool(prompt_lists["weather"])),
        "date_start": validated.date_start,
        "date_end": validated.date_end,
        "sexual_content_options": tuple(str(v) for v in config["sexual_content_options"]),
        "sexual_content_weights": tuple(float(v) for v in config["sexual_content_weights"]),
        "sexual_scene_tag_groups": sexual_scene_tag_groups,
        "sexual_scene_tag_group_names_sorted": tuple(stable_sorted_pool(sexual_scene_tag_groups)),
        "sexual_scene_tag_groups_sorted": {
            group_name: tuple(stable_sorted_pool(tags))
            for group_name, tags in sexual_scene_tag_groups.items()
        },
        "sexual_scene_tag_count_options": sexual_scene_tag_count_options,
        "sexual_scene_tag_count_weights": sexual_scene_tag_count_weights,
        "word_count_targets": tuple(int(v) for v in config["word_count_targets"]),
        "word_count_targets_sorted": tuple(
            stable_sorted_pool(int(v) for v in config["word_count_targets"])
        ),
        "ordered_keys": tuple(str(v) for v in config["ordered_keys"]),
        "writing_preamble": str(config["writing_preamble"]),
        "dataset_version": str(config["dataset_version"]),
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
