from datetime import timedelta

import pytest

from telegraphy.story_brief.generate_story_brief import (
    lint_story_data,
    load_story_data,
    validate_story_data,
    validate_story_data_strict,
)

def test_schema_validation_accepts_current_data(story_dataset_payloads) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    validate_story_data(titles, entities, prompts, config, partner_distributions)


@pytest.mark.parametrize(
    ("mutator", "expected_msg"),
    [
        (lambda t, e, p, c: c.pop("ordered_keys"), "missing required keys"),
        (lambda t, e, p, c: c.update({"dataset_version": ""}), "dataset_version"),
        (lambda t, e, p, c: c.update({"date_start": "not-a-date"}), "ISO dates"),
        (
            lambda t, e, p, c: c.update({"sexual_content_weights": [0, 0, 0, 0, 0]}),
            "must sum to > 0",
        ),
        (
            lambda t, e, p, c: c.update({"ordered_keys": c["ordered_keys"] + ["title"]}),
            "must not contain duplicates",
        ),
        (
            lambda t, e, p, c: c.update(
                {"ordered_keys": ["titel" if k == "title" else k for k in c["ordered_keys"]]}
            ),
            "ordered_keys mismatch",
        ),
        (lambda t, e, p, c: p.pop("weather"), "missing required keys"),
        (
            lambda t, e, p, c: e["setting_availability"].append(["Bad Row", 2020]),
            r"must be \[name, start, end\]",
        ),
        (
            lambda t, e, p, c: e["character_availability"].append(["Bool Year", True, 2000]),
            "boundary values must not be booleans",
        ),
        (
            lambda t, e, p, c: c.update({"word_count_targets": [True, 1200]}),
            "must be a positive integer",
        ),
        (
            lambda t, e, p, c: t.update({"titles": t["titles"] + [t["titles"][0]]}),
            "titles.titles contains duplicate value",
        ),
        (
            lambda t, e, p, c: p.update(
                {"weather": p["weather"] + [p["weather"][0]]}
            ),
            "prompts.weather contains duplicate value",
        ),
        (
            lambda t, e, p, c: e.update(
                {
                    "character_availability": e["character_availability"]
                    + [e["character_availability"][0]]
                }
            ),
            "overlapping availability windows",
        ),
        (
            lambda t, e, p, c: t.update({"titles": ["A Tale of @protagnoist"]}),
            "unsupported token",
        ),
        (
            lambda t, e, p, c: c.update(
                {"date_start": "1900-01-01", "date_end": "1900-12-31"}
            ),
            "no overlap with entities.character_availability",
        ),
        (
            lambda t, e, p, c: e.update(
                {"setting_availability": [["Far Future", "2100-01-01", "2100-12-31"]]}
            ),
            "no overlap with entities.setting_availability",
        ),
    ],
)
def test_schema_validation_rejects_bad_data(mutator, expected_msg: str, story_dataset_payloads) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    mutator(titles, entities, prompts, config)

    with pytest.raises(ValueError, match=expected_msg):
        validate_story_data(titles, entities, prompts, config, partner_distributions)


def test_schema_validation_allows_disjoint_availability_windows_for_same_name(
    story_dataset_payloads,
) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
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

    validate_story_data(titles, entities, prompts, config, partner_distributions)


def test_schema_validation_rejects_single_sexual_scene_tag_group(story_dataset_payloads) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    config["sexual_scene_tag_groups"] = {"tone": ["tender", "passionate"]}

    with pytest.raises(ValueError, match="at least 2 groups"):
        validate_story_data(titles, entities, prompts, config, partner_distributions)


def test_schema_validation_rejects_too_many_sexual_scene_tag_groups(story_dataset_payloads) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    config["sexual_scene_tag_groups"] = {
        f"group_{index}": [f"tag_{index}_a", f"tag_{index}_b"]
        for index in range(11)
    }

    with pytest.raises(ValueError, match="at most 10 groups"):
        validate_story_data(titles, entities, prompts, config, partner_distributions)


def test_schema_validation_rejects_duplicate_partners_in_single_era(story_dataset_payloads) -> None:
    titles = story_dataset_payloads["titles"]
    entities = story_dataset_payloads["entities"]
    prompts = story_dataset_payloads["prompts"]
    config = story_dataset_payloads["config"]
    partner_distributions = story_dataset_payloads["partner_distributions"]
    partner_distributions["partner_distributions"][0]["eras"][0]["partners"] = [
        {"partner": "Jordan", "weight": 0.7},
        {"partner": "jordan", "weight": 0.3},
    ]

    with pytest.raises(ValueError, match="contains duplicate partner"):
        validate_story_data(titles, entities, prompts, config, partner_distributions)


def test_strict_validation_accepts_well_formed_small_range() -> None:
    data = load_story_data()
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


def test_strict_validation_accepts_current_dataset_range() -> None:
    validate_story_data_strict(load_story_data())


def test_strict_validation_rejects_dates_with_fewer_than_two_distinct_characters() -> None:
    data = load_story_data()
    data["date_end"] = data["date_start"]
    data["character_availability"] = [
        ("Only One", data["date_start"], data["date_end"]),
    ]

    with pytest.raises(ValueError, match="fewer than two distinct available characters"):
        validate_story_data_strict(data)


def test_strict_validation_rejects_dates_with_no_settings() -> None:
    data = load_story_data()
    data["date_end"] = data["date_start"]
    data["setting_availability"] = []
    data["character_availability"] = [
        ("Alex", data["date_start"], data["date_end"]),
        ("Jordan", data["date_start"], data["date_end"]),
    ]

    with pytest.raises(ValueError, match="no available settings"):
        validate_story_data_strict(data)


def test_strict_validation_handles_max_date_boundary_without_overflow() -> None:
    max_day = load_story_data()["date_end"].replace(year=9999, month=12, day=31)
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
    data = load_story_data()
    data["date_end"] = data["date_start"]
    data["character_availability"] = [
        ("Only One", data["date_start"], data["date_end"]),
    ]
    data["setting_availability"] = []

    report = lint_story_data(data)

    assert report.has_errors
    assert any("fewer than two distinct characters" in msg for msg in report.errors)
    assert any("no available settings" in msg for msg in report.errors)


def test_dataset_lint_reports_non_blocking_warnings() -> None:
    data = load_story_data()
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
    assert any("weather has only 1 option(s)" in msg for msg in report.warnings)


def test_dataset_lint_reports_partner_data_coverage_gaps_by_protagonist() -> None:
    data = load_story_data()
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
    data = load_story_data()
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
    data = load_story_data()
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
