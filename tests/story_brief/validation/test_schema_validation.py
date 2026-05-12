import math
import re
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest

from telegraphy.story_brief.generate_story_brief import get_normalized_story_data
from telegraphy.story_brief.linting import lint_story_data
from telegraphy.story_brief.validation import (
    MAX_SEXUAL_SCENE_TAG_GROUPS,
    UNSUPPORTED_CONFIG_ALIAS_ERROR_PREFIX,
    UNSUPPORTED_CONFIG_ALIAS_KEYS,
    validate_story_data,
    validate_story_data_strict,
)

DEFAULT_TAG_COUNT_WEIGHTS_BY_PRESENCE = {
    "suggestive": {"1": 1.0},
    "explicit": {"1": 1.0},
    "implied": {"1": 1.0},
    "fade_to_black": {"1": 1.0},
}


def _tag_count_weights_with_none_entry(
    none_weights: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "none": none_weights,
        **DEFAULT_TAG_COUNT_WEIGHTS_BY_PRESENCE,
    }


def test_schema_validation_accepts_current_data(story_dataset_payloads) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    weather = story_dataset_payloads["weather"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    validate_story_data(titles, entities, prompts, weather, config, partner_distributions)


@pytest.mark.parametrize(
    ("mutator", "expected_msg"),
    [
        (lambda t, e, p, w, c: c.pop("ordered_keys"), "missing required keys"),
        (lambda t, e, p, w, c: c.update({"dataset_version": ""}), "dataset_version"),
        (lambda t, e, p, w, c: c.update({"date_start": "not-a-date"}), "ISO dates"),
        (
            lambda t, e, p, w, c: c.update({"sexual_content_presence_weights": [0, 0, 0, 0, 0]}),
            "must sum to > 0",
        ),
        (
            lambda t, e, p, w, c: c.update({"ordered_keys": c["ordered_keys"] + ["title"]}),
            "must not contain duplicates",
        ),
        (
            lambda t, e, p, w, c: c.update(
                {"ordered_keys": ["titel" if k == "title" else k for k in c["ordered_keys"]]}
            ),
            "ordered_keys mismatch",
        ),
        (lambda t, e, p, w, c: w.pop("weather"), "missing required keys"),
        (
            lambda t, e, p, w, c: e["setting_availability"].append(["Bad Row", 2020]),
            r"must be \[name, start, end\]",
        ),
        (
            lambda t, e, p, w, c: e["character_availability"].append(["Bool Year", True, 2000]),
            "boundary values must not be booleans",
        ),
        (
            lambda t, e, p, w, c: c.update({"word_count_targets": [True, 1200]}),
            "must be a positive integer",
        ),
        (
            lambda t, e, p, w, c: t.update({"titles": t["titles"] + [t["titles"][0]]}),
            "titles.titles contains duplicate value",
        ),
        (
            lambda t, e, p, w, c: w.update(
                {"weather": w["weather"] + [w["weather"][0]]}
            ),
            "weather.weather contains duplicate value",
        ),
        (
            lambda t, e, p, w, c: w.update({"weather_comment": "   "}),
            "weather.weather_comment must be a non-empty string when provided",
        ),
        (
            lambda t, e, p, w, c: w.update({"weather_comment": ["sunny"]}),
            "weather.weather_comment must be a non-empty string when provided",
        ),
        (
            lambda t, e, p, w, c: p.update({"unexpected_prompt_key": ["oops"]}),
            "prompts: unexpected keys: unexpected_prompt_key",
        ),
        (
            lambda t, e, p, w, c: e.update(
                {
                    "character_availability": e["character_availability"]
                    + [e["character_availability"][0]]
                }
            ),
            "overlapping availability windows",
        ),
        (
            lambda t, e, p, w, c: t.update({"titles": ["A Tale of @protagnoist"]}),
            "unsupported token",
        ),
        (
            lambda t, e, p, w, c: t.update({"titles": ["A Tale of protagonist"]}),
            "without '@'",
        ),
        (
            lambda t, e, p, w, c: c.update(
                {"date_start": "1900-01-01", "date_end": "1900-12-31"}
            ),
            "no overlap with entities.character_availability",
        ),
        (
            lambda t, e, p, w, c: e.update(
                {"setting_availability": [["Far Future", "2100-01-01", "2100-12-31"]]}
            ),
            "no overlap with entities.setting_availability",
        ),
    ],
)
def test_schema_validation_rejects_bad_data(
    mutator, expected_msg: str, story_dataset_payloads
) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    weather = story_dataset_payloads["weather"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    mutator(titles, entities, prompts, weather, config)

    with pytest.raises(ValueError, match=expected_msg):
        validate_story_data(titles, entities, prompts, weather, config, partner_distributions)


def test_schema_validation_allows_disjoint_availability_windows_for_same_name(
    story_dataset_payloads,
) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    weather = story_dataset_payloads["weather"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    entities["character_availability"] = [
        ["Alex", "2000-01-01", "2000-01-31"],
        ["Alex", "2000-03-01", "2000-03-31"],
        ["Jordan", "2000-01-01", "2000-12-31"],
    ]
    partner_distributions["partner_distributions"] = [
        {
            "character": "Alex",
            "date_start": "2000-01-01",
            "date_end": "2000-12-31",
            "eras": [
                {
                    "date_start": "2000-01-01",
                    "date_end": "2000-12-31",
                    "partners": [{"partner": "Jordan", "weight": 1.0}],
                }
            ],
        },
        {
            "character": "Jordan",
            "date_start": "2000-01-01",
            "date_end": "2000-12-31",
            "eras": [
                {
                    "date_start": "2000-01-01",
                    "date_end": "2000-12-31",
                    "partners": [{"partner": "Alex", "weight": 1.0}],
                }
            ],
        },
    ]

    validate_story_data(titles, entities, prompts, weather, config, partner_distributions)


def test_schema_validation_rejects_single_sexual_scene_tag_group(story_dataset_payloads) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    weather = story_dataset_payloads["weather"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    config["sexual_scene_tag_groups"] = {"tone": ["tender", "passionate"]}

    with pytest.raises(ValueError, match="at least 2 groups"):
        validate_story_data(titles, entities, prompts, weather, config, partner_distributions)


def test_schema_validation_rejects_too_many_sexual_scene_tag_groups(story_dataset_payloads) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    weather = story_dataset_payloads["weather"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    config["sexual_scene_tag_groups"] = {
        f"group_{index}": [f"tag_{index}_a", f"tag_{index}_b"]
        for index in range(MAX_SEXUAL_SCENE_TAG_GROUPS + 1)
    }

    with pytest.raises(
        ValueError,
        match=rf"at most {MAX_SEXUAL_SCENE_TAG_GROUPS} groups",
    ):
        validate_story_data(titles, entities, prompts, weather, config, partner_distributions)


@pytest.mark.parametrize(
    "unsupported_alias_key",
    UNSUPPORTED_CONFIG_ALIAS_KEYS,
)
def test_schema_validation_rejects_removed_config_alias_keys(
    unsupported_alias_key: str,
    story_dataset_payloads: dict[str, dict[str, Any]],
) -> None:
    _assert_schema_rejects(
        story_dataset_payloads,
        lambda t, e, p, w, c: c.update({unsupported_alias_key: ["legacy"]}),
        rf"{re.escape(UNSUPPORTED_CONFIG_ALIAS_ERROR_PREFIX)}.*{re.escape(unsupported_alias_key)}",
    )


def test_schema_validation_rejects_invalid_sexual_scene_tag_count_weight_key(
    story_dataset_payloads,
) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    weather = story_dataset_payloads["weather"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    config["sexual_scene_tag_count_weights_by_presence"] = {
        presence: {"abc": 1.0} for presence in config["sexual_content_presence_options"]
    }

    with pytest.raises(ValueError, match="keys must be non-negative integers"):
        validate_story_data(titles, entities, prompts, weather, config, partner_distributions)


def test_schema_validation_rejects_sexual_scene_tag_count_weight_above_group_count(
    story_dataset_payloads,
) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    weather = story_dataset_payloads["weather"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    group_count = len(config["sexual_scene_tag_groups"])
    config["sexual_scene_tag_count_weights_by_presence"] = {
        presence: {str(group_count + 1): 1.0}
        for presence in config["sexual_content_presence_options"]
    }

    with pytest.raises(ValueError, match="must not exceed the available"):
        validate_story_data(titles, entities, prompts, weather, config, partner_distributions)


def test_schema_validation_rejects_duplicate_partners_in_single_era(story_dataset_payloads) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    weather = story_dataset_payloads["weather"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    partner_distributions["partner_distributions"][0]["eras"][0]["partners"] = [
        {"partner": "Jordan", "weight": 0.7},
        {"partner": "jordan", "weight": 0.3},
    ]

    with pytest.raises(ValueError, match="contains duplicate partner"):
        validate_story_data(titles, entities, prompts, weather, config, partner_distributions)


def test_strict_validation_accepts_well_formed_small_range() -> None:
    data = get_normalized_story_data()
    start = data["date_start"]
    data["date_end"] = start
    data["character_availability"] = [
        ("Alex", start, start),
        ("Jordan", start, start),
    ]
    data["setting_availability"] = [
        ("Seattle", start, start),
    ]
    data["titles"] = ["A Night in @setting with @protagonist"]

    validate_story_data_strict(data)


def test_real_dataset_passes_strict_validation() -> None:
    validate_story_data_strict(get_normalized_story_data())


def test_strict_validation_rejects_dates_with_fewer_than_two_distinct_characters() -> None:
    data = get_normalized_story_data()
    data["date_end"] = data["date_start"]
    data["character_availability"] = [
        ("Only One", data["date_start"], data["date_end"]),
    ]

    with pytest.raises(ValueError, match="fewer than two distinct available characters"):
        validate_story_data_strict(data)


def test_strict_validation_rejects_dates_with_no_settings() -> None:
    data = get_normalized_story_data()
    data["date_end"] = data["date_start"]
    data["setting_availability"] = []
    data["character_availability"] = [
        ("Alex", data["date_start"], data["date_end"]),
        ("Jordan", data["date_start"], data["date_end"]),
    ]

    with pytest.raises(ValueError, match="no available settings"):
        validate_story_data_strict(data)


def test_strict_validation_handles_max_date_boundary_without_overflow() -> None:
    max_day = get_normalized_story_data()["date_end"].replace(year=9999, month=12, day=31)
    data = {
        "date_start": max_day,
        "date_end": max_day,
        "character_availability": [
            ("Alex", max_day, max_day),
            ("Jordan", max_day, max_day),
        ],
        "setting_availability": [
            ("Seattle", max_day, max_day),
        ],
        "titles": ["A Night in @setting"],
    }

    validate_story_data_strict(data)


def test_dataset_lint_reports_coverage_gap_errors() -> None:
    data = get_normalized_story_data()
    data["date_end"] = data["date_start"]
    data["character_availability"] = [
        ("Only One", data["date_start"], data["date_end"]),
    ]
    data["setting_availability"] = []

    report = lint_story_data(data)

    assert report.has_errors
    assert any("fewer than two distinct characters" in msg for msg in report.errors)
    assert any("no available settings" in msg for msg in report.errors)


def test_dataset_lint_handles_max_date_boundary_without_excluding_final_day() -> None:
    max_day = get_normalized_story_data()["date_end"].replace(year=9999, month=12, day=31)
    data = {
        "date_start": max_day,
        "date_end": max_day,
        "character_availability": [
            ("Only One", max_day, max_day),
        ],
        "setting_availability": [],
        "partner_distributions": {},
        "titles": ["A Night in @setting"],
        "central_conflicts": ["One", "Two", "Three"],
        "inciting_pressures": ["One", "Two", "Three"],
        "ending_types": ["One", "Two", "Three"],
        "style_guidance": ["One", "Two", "Three"],
        "weather": ["One", "Two", "Three"],
        "word_count_targets": [700, 900, 1200],
    }

    report = lint_story_data(data)

    assert report.has_errors
    assert any("fewer than two distinct characters" in msg for msg in report.errors)
    assert any("no available settings" in msg for msg in report.errors)


def test_dataset_lint_reports_non_blocking_warnings() -> None:
    data = get_normalized_story_data()
    day = data["date_start"]
    data["date_end"] = day
    data["character_availability"] = [
        ("Alex", day, day),
        ("Jordan", day, day),
    ]
    data["setting_availability"] = [
        ("Seattle", day, day),
    ]
    data["titles"] = ["A Night in @setting"]
    data["weather"] = ["Rain"]
    data["word_count_targets"] = [700]

    report = lint_story_data(data)

    assert not report.has_errors
    assert any("exactly two characters" in msg for msg in report.warnings)
    assert any("exactly one setting" in msg for msg in report.warnings)
    assert any("token(s) never used" in msg for msg in report.warnings)
    assert any("weather has only 1 option;" in msg for msg in report.warnings)


def test_dataset_lint_reports_partner_data_coverage_gaps_by_protagonist() -> None:
    data = get_normalized_story_data()
    day = data["date_start"]
    data["date_end"] = day
    data["character_availability"] = [
        ("Alex", day, day),
        ("Jordan", day, day),
    ]
    data["setting_availability"] = [
        ("Seattle", day, day),
    ]
    data["partner_distributions"] = {
        "Alex": [
            {"date_start": day, "date_end": day, "partners": [("Jordan", 1.0)]},
        ],
        "Jordan": [],
    }

    report = lint_story_data(data)

    assert not report.has_errors
    assert any(
        "Partner data coverage gap: protagonist 'Jordan' has no partner era data available on "
        in msg
        and day.isoformat() in msg
        for msg in report.warnings
    )


def test_dataset_lint_uses_partner_era_boundaries_for_gap_detection() -> None:
    data = get_normalized_story_data()
    day = data["date_start"]
    next_day = day + timedelta(days=1)
    data["date_end"] = next_day
    data["character_availability"] = [
        ("Alex", day, next_day),
        ("Jordan", day, next_day),
    ]
    data["setting_availability"] = [
        ("Seattle", day, next_day),
    ]
    data["partner_distributions"] = {
        "Alex": [
            {"date_start": day, "date_end": day, "partners": [("Jordan", 1.0)]},
        ],
        "Jordan": [
            {"date_start": day, "date_end": next_day, "partners": [("Alex", 1.0)]},
        ],
    }

    report = lint_story_data(data)

    assert not report.has_errors
    assert any(
        "Partner data coverage gap: protagonist 'Alex' has no partner era data available on "
        in msg
        and next_day.isoformat() in msg
        for msg in report.warnings
    )


def test_dataset_lint_treats_empty_partner_eras_as_intentional_celibacy() -> None:
    data = get_normalized_story_data()
    day = data["date_start"]
    data["date_end"] = day
    data["character_availability"] = [
        ("Alex", day, day),
        ("Jordan", day, day),
    ]
    data["setting_availability"] = [
        ("Seattle", day, day),
    ]
    data["partner_distributions"] = {
        "Alex": [
            {"date_start": day, "date_end": day, "partners": [("Jordan", 1.0)]},
        ],
        "Jordan": [
            {"date_start": day, "date_end": day, "partners": []},
        ],
    }

    report = lint_story_data(data)

    assert not report.has_errors
    assert not any(
        "Partner data coverage gap: protagonist 'Jordan'" in msg
        for msg in report.warnings
    )


PayloadMutator = Callable[
    [dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
    None,
]


def _assert_schema_rejects(
    story_dataset_payloads: dict[str, dict[str, Any]],
    mutator: PayloadMutator,
    expected_message: str,
) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    weather = story_dataset_payloads["weather"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    mutator(titles, entities, prompts, weather, config)

    with pytest.raises(ValueError, match=expected_message):
        validate_story_data(titles, entities, prompts, weather, config, partner_distributions)


def _set_minimal_partner_distributions(partner_distributions: dict[str, Any]) -> None:
    partner_distributions.clear()
    partner_distributions.update(
        {
            "schema_version": 1,
            "dataset_version": "branch-condition-test",
            "date_start": "2000-01-01",
            "date_end": "2000-01-01",
            "partner_distributions": [
                {
                    "character": "Alex",
                    "date_start": "2000-01-01",
                    "date_end": "2000-01-01",
                    "eras": [
                        {
                            "date_start": "2000-01-01",
                            "date_end": "2000-01-01",
                            "partners": [{"partner": "Jordan", "weight": 1.0}],
                        }
                    ],
                },
                {
                    "character": "Jordan",
                    "date_start": "2000-01-01",
                    "date_end": "2000-01-01",
                    "eras": [
                        {
                            "date_start": "2000-01-01",
                            "date_end": "2000-01-01",
                            "partners": [{"partner": "Alex", "weight": 1.0}],
                        }
                    ],
                },
            ],
        }
    )


@pytest.mark.parametrize(
    ("mutator", "expected_message"),
    [
        (
            lambda titles, _entities, _prompts, _weather, _config: titles.update({"titles": []}),
            r"titles\.titles must be a non-empty list",
        ),
        (
            lambda _titles, _entities, _prompts, weather, _config: weather.update(
                {"weather": [" "]}
            ),
            r"weather\.weather\[0\] must be a non-empty string",
        ),
        (
            lambda _titles, entities, _prompts, _weather, _config: entities.update(
                {"character_availability": []}
            ),
            r"entities\.character_availability must be a non-empty list",
        ),
        (
            lambda _titles, entities, _prompts, _weather, _config: entities[
                "character_availability"
            ].append(["Bad Date", "not-a-date", 2000]),
            r"boundary string values must be ISO dates",
        ),
        (
            lambda _titles, entities, _prompts, _weather, _config: entities[
                "character_availability"
            ].append(["Integer Boundary", 2000, "2000-12-31"]),
            r"boundary values must be ISO date strings \(YYYY-MM-DD\)",
        ),
        (
            lambda _titles, entities, _prompts, _weather, _config: entities[
                "character_availability"
            ].append(["Bad Boundary", None, 2000]),
            r"boundary values must be ISO date strings \(YYYY-MM-DD\)",
        ),
        (
            lambda _titles, entities, _prompts, _weather, _config: entities[
                "character_availability"
            ].append([" ", 2000, 2001]),
            r"entities\.character_availability\[\d+\]\[0\] must be a non-empty string",
        ),
        (
            lambda _titles, entities, _prompts, _weather, _config: entities[
                "character_availability"
            ].append(["Backward", "2001-01-01", "2000-01-01"]),
            r"start must be <= end",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update({"schema_version": 0}),
            r"config\.schema_version must be an integer >= 1",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"date_start": "2001-01-01", "date_end": "2000-01-01"}
            ),
            r"config\.date_start must be <= config\.date_end",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_content_presence_weights": []}
            ),
            r"config\.sexual_content_presence_weights must be a non-empty list",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_content_presence_weights": [1.0]}
            ),
            (
                r"config sexual_content_presence_options/"
                r"sexual_content_presence_weights must be the same length"
            ),
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_content_presence_weights": [True, 1.0, 1.0, 1.0, 1.0]}
            ),
            r"config\.sexual_content_presence_weights\[0\] must be a real number",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_content_presence_weights": [math.inf, 1.0, 1.0, 1.0, 1.0]}
            ),
            r"config\.sexual_content_presence_weights\[0\] must be finite",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_content_presence_weights": [-1.0, 1.0, 1.0, 1.0, 1.0]}
            ),
            r"config\.sexual_content_presence_weights\[0\] must be non-negative",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"word_count_targets": []}
            ),
            r"config\.word_count_targets must be a non-empty list",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_scene_tag_groups": {}}
            ),
            r"config\.sexual_scene_tag_groups must be a non-empty object",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_scene_tag_groups": {"": ["one"], "tone": ["two"]}}
            ),
            r"config\.sexual_scene_tag_groups keys must be non-empty strings",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_scene_tag_count_weights_by_presence": {}}
            ),
            r"config\.sexual_scene_tag_count_weights_by_presence must be a non-empty object",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {
                    "sexual_scene_tag_count_weights_by_presence": (
                        _tag_count_weights_with_none_entry({"abc": 1.0})
                    )
                }
            ),
            r"sexual_scene_tag_count_weights_by_presence\.none keys must be non-negative integers",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {
                    "sexual_scene_tag_count_weights_by_presence": (
                        _tag_count_weights_with_none_entry({"1": 0.0, "2": 0.0})
                    )
                }
            ),
            r"sexual_scene_tag_count_weights_by_presence\.none values must sum to > 0",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {
                    "sexual_scene_tag_count_weights_by_presence": (
                        _tag_count_weights_with_none_entry({"1": True})
                    )
                }
            ),
            r"sexual_scene_tag_count_weights_by_presence\.none values must be real numbers",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {
                    "sexual_scene_tag_count_weights_by_presence": (
                        _tag_count_weights_with_none_entry({"1": math.inf})
                    )
                }
            ),
            r"sexual_scene_tag_count_weights_by_presence\.none values must be finite",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {
                    "sexual_scene_tag_count_weights_by_presence": (
                        _tag_count_weights_with_none_entry({"1": -1.0})
                    )
                }
            ),
            r"sexual_scene_tag_count_weights_by_presence\.none values must be non-negative",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_scene_optional_tag_groups": ["unknown"]}
            ),
            r"config\.sexual_scene_optional_tag_groups contains unknown groups: unknown",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_scene_optional_tag_groups": ["tone", "tone"]}
            ),
            r"config\.sexual_scene_optional_tag_groups contains duplicate value at index 1",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_scene_optional_tag_groups": ["tone", " "]}
            ),
            r"config\.sexual_scene_optional_tag_groups\[1\] must be a non-empty string",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_scene_required_tag_groups_by_presence": {"unknown": ["tone"]}}
            ),
            (
                r"config\.sexual_scene_required_tag_groups_by_presence contains unknown "
                r"presence options: unknown"
            ),
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {
                    "sexual_scene_required_tag_groups_by_presence": {
                        "none": [],
                    }
                }
            ),
            (
                r"config\.sexual_scene_required_tag_groups_by_presence is missing required "
                r"presence options: explicit, fade_to_black, implied, suggestive"
            ),
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_scene_required_tag_groups_by_presence": {"none": ["unknown"]}}
            ),
            (
                r"config\.sexual_scene_required_tag_groups_by_presence\.none contains unknown "
                r"groups: unknown"
            ),
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"sexual_scene_required_tag_groups_by_presence": {"none": ["tone", "tone"]}}
            ),
            (
                r"config\.sexual_scene_required_tag_groups_by_presence\.none contains duplicate "
                r"value at index 1"
            ),
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {
                    "sexual_scene_required_tag_groups_by_presence": {
                        "none": ["tone", " "],
                        **{
                            key: value
                            for key, value in config[
                                "sexual_scene_required_tag_groups_by_presence"
                            ].items()
                            if key != "none"
                        },
                    }
                }
            ),
            (
                r"config\.sexual_scene_required_tag_groups_by_presence\.none\[1\] must be a "
                r"non-empty string"
            ),
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: (
                config["sexual_scene_tag_count_weights_by_presence"]
                .setdefault("none", {})
                .update({"1": 1.0, "2": 0.0}),
                config.update(
                    {
                        "sexual_scene_required_tag_groups_by_presence": {
                            "none": list(config["sexual_scene_tag_groups"].keys())[:2],
                            **{
                                key: value
                                for key, value in config[
                                    "sexual_scene_required_tag_groups_by_presence"
                                ].items()
                                if key != "none"
                            },
                        }
                    }
                ),
            ),
            (
                r"config\.sexual_scene_required_tag_groups_by_presence\.none requires 2 groups, "
                r"but config\.sexual_scene_tag_count_weights_by_presence\.none allows as few "
                r"as 0 tags"
            ),
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: (
                config["sexual_scene_tag_count_weights_by_presence"]
                .setdefault("none", {})
                .update({"0": 1.0, "1": 1.0}),
                config.update(
                    {
                        "sexual_scene_required_tag_groups_by_presence": {
                            "none": ["tone"],
                            **{
                                key: value
                                for key, value in config[
                                    "sexual_scene_required_tag_groups_by_presence"
                                ].items()
                                if key != "none"
                            },
                        }
                    }
                ),
            ),
            (
                r"config\.sexual_scene_required_tag_groups_by_presence\.none requires 1 group, "
                r"but config\.sexual_scene_tag_count_weights_by_presence\.none allows as few "
                r"as 0 tags"
            ),
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update({"ordered_keys": []}),
            r"config\.ordered_keys must be a non-empty list",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"ordered_keys": [" ", *config["ordered_keys"][1:]]}
            ),
            r"config\.ordered_keys\[0\] must be a non-empty string",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"ordered_keys": [key for key in config["ordered_keys"] if key != "title"]}
            ),
            r"missing expected keys: title",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update(
                {"ordered_keys": [*config["ordered_keys"], "bonus_field"]}
            ),
            r"unexpected keys: bonus_field",
        ),
        (
            lambda _titles, _entities, _prompts, _weather, config: config.update({"writing_preamble": ""}),
            r"config\.writing_preamble must be a non-empty string",
        ),
    ],
)
def test_schema_validation_rejects_uncovered_branch_conditions(
    story_dataset_payloads: dict[str, dict[str, Any]],
    mutator: PayloadMutator,
    expected_message: str,
) -> None:
    _assert_schema_rejects(story_dataset_payloads, mutator, expected_message)
