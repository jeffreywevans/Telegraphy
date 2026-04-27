import random

import pytest

from telegraphy.story_brief.generation import symmetric_peak_weights, weighted_choice


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
