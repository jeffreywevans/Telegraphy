import random

import pytest

from telegraphy.story_brief.generation import (
    build_sexual_scene_tag_count_distribution,
    symmetric_peak_weights,
    weighted_choice,
)


def test_weighted_choice_returns_option_from_domain() -> None:
    rng = random.Random(1)
    options = ["a", "b", "c"]
    weights = [0.6, 0.3, 0.1]

    value = weighted_choice(rng, options, weights)
    assert value in options


def test_weighted_choice_supports_non_string_options() -> None:
    rng = random.Random(3)
    options = [2, 3, 4]
    weights = [0.7, 0.2, 0.1]

    value = weighted_choice(rng, options, weights)
    assert value in options


@pytest.mark.parametrize(
    ("options", "weights", "expected_exc"),
    [
        ([], [], ValueError),
        (["a"], [], ValueError),
        (["a", "b"], [1.0], ValueError),
        (["a"], [float("nan")], ValueError),
        (["a"], [float("inf")], ValueError),
        (["a"], [-1.0], ValueError),
        (["a"], [0.0], ValueError),
        (["a"], [True], TypeError),
        (["a"], ["x"], TypeError),
    ],
)
def test_weighted_choice_invalid_inputs(options, weights, expected_exc) -> None:
    rng = random.Random(1)
    with pytest.raises(expected_exc):
        weighted_choice(rng, options, weights)


def test_weighted_choice_never_selects_zero_weight_option() -> None:
    rng = random.Random(42)
    options = ["disabled", "enabled"]
    weights = [0.0, 1.0]

    for _ in range(100):
        assert weighted_choice(rng, options, weights) == "enabled"


def test_symmetric_peak_weights_shape_for_odd_length() -> None:
    assert symmetric_peak_weights(5) == (1, 2, 3, 2, 1)


def test_symmetric_peak_weights_shape_for_even_length() -> None:
    assert symmetric_peak_weights(4) == (1, 2, 2, 1)


def test_symmetric_peak_weights_rejects_non_positive_lengths() -> None:
    for length in (0, -1):
        with pytest.raises(ValueError, match="greater than zero"):
            symmetric_peak_weights(length)


def test_count_distribution_presence_fallback_respects_minimum_count_off_page() -> None:
    data = {
        "sexual_scene_tag_count_options": (3, 4),
        "sexual_scene_tag_count_weights": (0.5, 0.5),
    }

    with pytest.raises(
        ValueError,
        match="No valid sexual scene tag count options remain",
    ):
        build_sexual_scene_tag_count_distribution(("tone", "location"), data)


def test_build_sexual_scene_tag_count_distribution_supports_mapping_weights() -> None:
    data = {
        "sexual_scene_tag_count_options": (2, 1),
        "sexual_scene_tag_count_weights": {"1": 0.75, "2": 0.25},
    }

    options, weights = build_sexual_scene_tag_count_distribution(
        ("tone", "location"), data
    )

    assert options == [2, 1]
    assert weights == [0.25, 0.75]


def test_build_sexual_scene_tag_count_distribution_mapping_missing_key_defaults_zero() -> None:
    data = {
        "sexual_scene_tag_count_options": (1, 2),
        "sexual_scene_tag_count_weights": {"1": 1.0},
    }

    options, weights = build_sexual_scene_tag_count_distribution(
        ("tone", "location"), data
    )

    assert options == [1, 2]
    assert weights == [1.0, 0.0]


def test_build_sexual_scene_tag_count_distribution_mapping_null_value_defaults_zero() -> None:
    data = {
        "sexual_scene_tag_count_options": (1, 2),
        "sexual_scene_tag_count_weights": {"1": 1.0, "2": None},
    }

    options, weights = build_sexual_scene_tag_count_distribution(
        ("tone", "location"), data
    )

    assert options == [1, 2]
    assert weights == [1.0, 0.0]


def test_build_sexual_scene_tag_count_distribution_empty_mapping_falls_back_to_defaults() -> None:
    data = {
        "sexual_scene_tag_count_options": (2, 3),
        "sexual_scene_tag_count_weights": {},
    }

    options, weights = build_sexual_scene_tag_count_distribution(
        ("tone", "location", "dynamic"), data
    )

    assert options == [2, 3]
    assert weights == [0.7, 0.1]


def test_build_sexual_scene_tag_count_distribution_filters_below_minimum_count() -> None:
    data = {
        "sexual_scene_tag_count_options": (2, 3, 4),
        "sexual_scene_tag_count_weights": (0.5, 0.3, 0.2),
    }

    options, weights = build_sexual_scene_tag_count_distribution(
        ("tone", "location", "pacing", "aftermath"),
        data,
        minimum_count=3,
    )

    assert options == [3, 4]
    assert weights == [0.3, 0.2]


def test_pick_sexual_scene_tags_enforces_required_groups_and_optional_pool() -> None:
    from telegraphy.story_brief.generation import pick_sexual_scene_tags

    rng = random.Random(7)
    data = {
        "sexual_scene_tag_group_names_sorted": (
            "aftermath",
            "location",
            "physicality",
            "pacing",
            "tone",
        ),
        "sexual_scene_tag_groups_sorted": {
            "aftermath": ("after",),
            "location": ("loc",),
            "physicality": ("phys",),
            "pacing": ("pace",),
            "tone": ("tone",),
        },
        "sexual_scene_tag_count_weights_by_presence": {
            "on_page_full": {5: 1.0}
        },
        "sexual_scene_required_tag_groups_by_presence": {
            "on_page_full": ("location", "tone", "aftermath"),
        },
        "sexual_scene_optional_tag_groups": ("pacing", "physicality"),
    }

    selected_tags = pick_sexual_scene_tags(rng, "on_page_full", data)

    assert set(selected_tags) == {"loc", "tone", "after", "pace", "phys"}


def test_count_distribution_presence_fallback_respects_minimum_count() -> None:
    data = {
        "sexual_scene_tag_count_weights_by_presence": {
            "on_page_full": {1: 1.0}
        }
    }

    options, weights = build_sexual_scene_tag_count_distribution(
        ("a", "b", "c", "d", "e"),
        data,
        sexual_content_presence="off_page",
        minimum_count=4,
    )

    assert options == [4, 5]
    assert weights == [0.1, 0.1]
