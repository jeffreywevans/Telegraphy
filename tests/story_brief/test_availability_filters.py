from datetime import date

from telegraphy.story_brief import generate_story_brief as story_brief
from telegraphy.story_brief.generation import available_characters, available_settings


def test_available_characters_filters_by_date() -> None:
    data = dict(story_brief.get_data())
    data["character_availability"] = [
        ("Alex", date(2000, 1, 1), date(2001, 12, 31)),
        ("Jordan", date(2002, 1, 1), date(2003, 12, 31)),
        ("Casey", date(2001, 6, 1), date(2002, 6, 30)),
    ]
    assert available_characters(date(2001, 1, 1), data) == ["Alex"]
    assert available_characters(date(2002, 1, 1), data) == ["Jordan", "Casey"]
    assert available_characters(date(1999, 12, 31), data) == []


def test_available_settings_filters_by_date() -> None:
    data = dict(story_brief.get_data())
    data["setting_availability"] = [
        ("Seattle", date(2000, 1, 1), date(2000, 12, 31)),
        ("Portland", date(2000, 6, 1), date(2001, 6, 30)),
    ]
    assert available_settings(date(2000, 1, 1), data) == ["Seattle"]
    assert available_settings(date(2000, 7, 1), data) == ["Seattle", "Portland"]
    assert available_settings(date(2001, 7, 1), data) == []
