"""Narrow compatibility checks for legacy `generate_story_brief` façade exports."""

import pytest

from telegraphy.story_brief import cli
from telegraphy.story_brief import generate_story_brief as legacy


def test_legacy_facade_still_exposes_main_entrypoints() -> None:
    assert callable(legacy.pick_story_fields)
    assert callable(legacy.to_markdown)
    assert callable(legacy.build_auto_filename)
    assert callable(cli.main)


def test_legacy_compat_alias_attribute_resolves_to_data_copy() -> None:
    titles = legacy.TITLES

    assert isinstance(titles, tuple)
    assert titles == legacy.get_data()["titles"]

    groups_1 = legacy.SEXUAL_SCENE_TAG_GROUPS
    groups_2 = legacy.SEXUAL_SCENE_TAG_GROUPS

    assert isinstance(groups_1, dict)
    assert groups_1 is not groups_2
    assert groups_1 == legacy.get_data()["sexual_scene_tag_groups"]


def test_legacy_unknown_attribute_raises_attribute_error() -> None:
    with pytest.raises(AttributeError, match=r"has no attribute 'DOES_NOT_EXIST'"):
        _ = legacy.DOES_NOT_EXIST
