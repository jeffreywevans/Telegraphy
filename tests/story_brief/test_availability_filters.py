from datetime import date

import pytest

from commuted_calligraphy.story_brief import generate_story_brief as story_brief


def test_available_characters_filters_by_date(monkeypatch: pytest.MonkeyPatch) -> None:
    data = dict(story_brief.get_data())
    data["character_availability"] = [
        ("Alex", date(2000, 1, 1), date(2001, 12, 31)),
        ("Jordan", date(2002, 1, 1), date(2003, 12, 31)),
        ("Casey", date(2001, 6, 1), date(2002, 6, 30)),
    ]
    monkeypatch.setattr(story_brief, "get_data", lambda: data)

    assert story_brief.available_characters(date(2001, 1, 1)) == ["Alex"]
    assert story_brief.available_characters(date(2002, 1, 1)) == ["Jordan", "Casey"]
    assert story_brief.available_characters(date(1999, 12, 31)) == []


def test_available_settings_filters_by_date(monkeypatch: pytest.MonkeyPatch) -> None:
    data = dict(story_brief.get_data())
    data["setting_availability"] = [
        ("Seattle", date(2000, 1, 1), date(2000, 12, 31)),
        ("Portland", date(2000, 6, 1), date(2001, 6, 30)),
    ]
    monkeypatch.setattr(story_brief, "get_data", lambda: data)

    assert story_brief.available_settings(date(2000, 1, 1)) == ["Seattle"]
    assert story_brief.available_settings(date(2000, 7, 1)) == ["Seattle", "Portland"]
    assert story_brief.available_settings(date(2001, 7, 1)) == []
