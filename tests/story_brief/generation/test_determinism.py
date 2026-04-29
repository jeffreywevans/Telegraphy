import random
from collections import defaultdict
from copy import deepcopy
from datetime import date

import pytest

from telegraphy.story_brief.generate_story_brief import get_data, pick_story_fields


def test_same_seed_is_deterministic() -> None:
    fields_a = pick_story_fields(random.Random(12345))
    fields_b = pick_story_fields(random.Random(12345))
    assert fields_a == fields_b


def test_different_seeds_typically_differ() -> None:
    fields_a = pick_story_fields(random.Random(100))
    fields_b = pick_story_fields(random.Random(101))
    assert fields_a != fields_b


def test_secondary_character_differs_from_protagonist() -> None:
    for seed in range(50):
        fields = pick_story_fields(random.Random(seed))
        assert fields["secondary_character"] != fields["protagonist"]


def test_explicit_date_overrides_random_date() -> None:
    fields = pick_story_fields(random.Random(999), selected_date=date(2000, 1, 1))
    assert fields["time_period"] == "2000-01-01"


def test_explicit_date_out_of_range_fails() -> None:
    with pytest.raises(ValueError, match="outside available range"):
        pick_story_fields(random.Random(1), selected_date=date(1900, 1, 1))


@pytest.mark.slow
def test_selected_characters_are_valid_for_time_period_year() -> None:
    availability: dict[str, list[tuple[date, date]]] = defaultdict(list)
    for name, start, end in get_data()["character_availability"]:
        availability[name].append((start, end))

    for seed in range(200):
        fields = pick_story_fields(random.Random(seed))
        selected = date.fromisoformat(str(fields["time_period"]))

        protagonist = str(fields["protagonist"])
        secondary = str(fields["secondary_character"])

        assert any(start <= selected <= end for start, end in availability[protagonist])
        assert any(start <= selected <= end for start, end in availability[secondary])


def test_duplicate_character_rows_require_two_distinct_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from telegraphy.story_brief import generate_story_brief as story_brief

    data = dict(story_brief.get_data())
    data["character_availability"] = [
        ("Only Name", date(2000, 1, 1), date(2000, 12, 31)),
        ("Only Name", date(2000, 1, 1), date(2000, 12, 31)),
    ]
    monkeypatch.setattr(story_brief, "get_data", lambda: data)

    with pytest.raises(ValueError, match="two distinct available characters"):
        pick_story_fields(random.Random(7), selected_date=date(2000, 1, 1))


def test_weather_value_is_from_allowed_pool() -> None:
    allowed = set(get_data()["weather"])
    for seed in range(25):
        fields = pick_story_fields(random.Random(seed))
        assert fields["weather"] in allowed


@pytest.mark.slow
def test_sexual_scene_tags_follow_count_and_group_rules() -> None:
    tag_groups = get_data()["sexual_scene_tag_groups"]
    tag_to_group = {
        tag: group_name
        for group_name, tags in tag_groups.items()
        for tag in tags
    }

    for seed in range(200):
        fields = pick_story_fields(random.Random(seed))
        sexual_content_level = fields["sexual_content_level"]
        selected_tags = fields["sexual_scene_tags"]

        assert isinstance(selected_tags, list)
        if sexual_content_level == "none":
            assert selected_tags == []
            assert fields["sexual_partner"] is None
            continue

        assert 2 <= len(selected_tags) <= 5
        assert len(selected_tags) == len(set(selected_tags))

        selected_groups = {tag_to_group[tag] for tag in selected_tags}
        assert len(selected_groups) == len(selected_tags)
        assert fields["sexual_partner"] is None or isinstance(fields["sexual_partner"], str)


def test_non_none_sexual_content_with_positive_partner_weight_requires_partner_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from telegraphy.story_brief import generate_story_brief as story_brief

    data = story_brief.get_data()
    selected_date = date(2000, 1, 1)
    protagonist = "Alex"

    data["character_availability"] = [
        (protagonist, selected_date, selected_date),
        ("Jordan", selected_date, selected_date),
    ]
    data["setting_availability"] = [("Seattle", selected_date, selected_date)]
    data["sexual_content_options"] = ["none", "suggestive"]
    data["sexual_content_weights"] = [0.0, 1.0]
    data[story_brief.PARTNER_DISTRIBUTIONS_KEY][protagonist] = [
        {
            "date_start": selected_date,
            "date_end": selected_date,
            "partners": [("Jordan", 1.0)],
        }
    ]
    data[story_brief.PARTNER_DISTRIBUTIONS_KEY]["Jordan"] = [
        {
            "date_start": selected_date,
            "date_end": selected_date,
            "partners": [(protagonist, 1.0)],
        }
    ]
    monkeypatch.setattr(story_brief, "get_data", lambda: data)
    fields = story_brief.pick_story_fields(random.Random(123), selected_date=selected_date)

    assert fields["sexual_content_level"] != "none"
    assert fields["sexual_partner"] == (
        "Jordan" if fields["protagonist"] == protagonist else protagonist
    )


def test_seed_output_is_stable_when_option_pool_order_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from telegraphy.story_brief import generate_story_brief as story_brief

    baseline_data = story_brief.get_data()
    # Deep copy is intentional here so list/dict reordering does not mutate baseline_data.
    shuffled_data = deepcopy(baseline_data)

    shuffled_data["setting_availability"] = list(reversed(shuffled_data["setting_availability"]))
    shuffled_data["titles"] = list(reversed(shuffled_data["titles"]))
    shuffled_data["central_conflicts"] = list(reversed(shuffled_data["central_conflicts"]))
    shuffled_data["inciting_pressures"] = list(reversed(shuffled_data["inciting_pressures"]))
    shuffled_data["ending_types"] = list(reversed(shuffled_data["ending_types"]))
    shuffled_data["style_guidance"] = list(reversed(shuffled_data["style_guidance"]))
    shuffled_data["word_count_targets"] = list(reversed(shuffled_data["word_count_targets"]))
    shuffled_data["sexual_scene_tag_groups"] = {
        group_name: list(reversed(tags))
        for group_name, tags in reversed(
            list(shuffled_data["sexual_scene_tag_groups"].items())
        )
    }

    seed = 8675309
    selected_date = date(2026, 1, 1)
    monkeypatch.setattr(story_brief, "get_data", lambda: baseline_data)
    baseline_fields = story_brief.pick_story_fields(
        random.Random(seed), selected_date=selected_date
    )

    monkeypatch.setattr(story_brief, "get_data", lambda: shuffled_data)
    shuffled_fields = story_brief.pick_story_fields(
        random.Random(seed), selected_date=selected_date
    )

    assert shuffled_fields == baseline_fields


def test_pick_story_fields_reads_data_once_per_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from telegraphy.story_brief import generate_story_brief as story_brief

    calls = {"count": 0}
    data = story_brief.get_data()

    def counting_get_data() -> dict[str, object]:
        calls["count"] += 1
        return data

    monkeypatch.setattr(story_brief, "get_data", counting_get_data)
    story_brief.pick_story_fields(random.Random(321), selected_date=date(2000, 1, 1))

    assert calls["count"] == 1


def test_pick_story_fields_handles_partner_distribution_gap_year(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from telegraphy.story_brief import generate_story_brief as story_brief

    selected_date = date(2000, 1, 1)
    data = story_brief.get_data()
    data["character_availability"] = [
        ("Alex", selected_date, selected_date),
        ("Jordan", selected_date, selected_date),
    ]
    data["setting_availability"] = [("Seattle", selected_date, selected_date)]
    data["sexual_content_options"] = ["suggestive"]
    data["sexual_content_weights"] = [1.0]
    gap_eras = [
        {
            "date_start": date(1999, 1, 1),
            "date_end": date(1999, 12, 31),
            "partners": [("Jordan", 1.0)],
        },
        {
            "date_start": date(2001, 1, 1),
            "date_end": date(2001, 12, 31),
            "partners": [("Jordan", 1.0)],
        },
    ]
    data[story_brief.PARTNER_DISTRIBUTIONS_KEY]["Alex"] = gap_eras
    data[story_brief.PARTNER_DISTRIBUTIONS_KEY]["Jordan"] = gap_eras

    monkeypatch.setattr(story_brief, "get_data", lambda: data)
    fields = story_brief.pick_story_fields(random.Random(9), selected_date=selected_date)

    assert fields["sexual_content_level"] == "suggestive"
    assert fields["sexual_partner"] is None


def test_pick_story_fields_handles_missing_partner_distribution_for_protagonist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from telegraphy.story_brief import generate_story_brief as story_brief

    selected_date = date(2000, 1, 1)
    data = story_brief.get_data()
    data["character_availability"] = [
        ("Alex", selected_date, selected_date),
        ("Jordan", selected_date, selected_date),
    ]
    data["setting_availability"] = [("Seattle", selected_date, selected_date)]
    data["sexual_content_options"] = ["suggestive"]
    data["sexual_content_weights"] = [1.0]
    data[story_brief.PARTNER_DISTRIBUTIONS_KEY].pop("Alex", None)
    data[story_brief.PARTNER_DISTRIBUTIONS_KEY].pop("Jordan", None)

    monkeypatch.setattr(story_brief, "get_data", lambda: data)
    fields = story_brief.pick_story_fields(random.Random(1), selected_date=selected_date)

    assert fields["sexual_content_level"] == "suggestive"
    assert fields["sexual_partner"] is None
