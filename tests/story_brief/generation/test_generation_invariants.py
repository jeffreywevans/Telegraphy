from __future__ import annotations

from datetime import date, timedelta

import pytest

from telegraphy.story_brief.generate_story_brief import get_normalized_story_data as get_data
from telegraphy.story_brief.generation_invariants import validate_story_data_strict


def test_strict_invariants_pass_for_normalized_story_data() -> None:
    """Characterization guard: current production dataset must satisfy strict checks."""
    validate_story_data_strict(get_data())


def test_strict_invariants_fail_when_date_has_only_one_distinct_character() -> None:
    selected_date = date(2000, 1, 1)
    end_date = selected_date + timedelta(days=1)
    data = {
        "date_start": selected_date,
        "date_end": end_date,
        "character_availability": (("Alex", selected_date, end_date),),
        "setting_availability": (("Seattle", selected_date, end_date),),
    }

    with pytest.raises(ValueError, match="fewer than two distinct available characters"):
        validate_story_data_strict(data)


def test_strict_invariants_fail_when_date_has_no_available_setting() -> None:
    selected_date = date(2000, 1, 1)
    data = {
        "date_start": selected_date,
        "date_end": selected_date,
        "character_availability": (
            ("Alex", selected_date, selected_date),
            ("Jordan", selected_date, selected_date),
        ),
        "setting_availability": (),
    }

    with pytest.raises(ValueError, match="no available settings"):
        validate_story_data_strict(data)
