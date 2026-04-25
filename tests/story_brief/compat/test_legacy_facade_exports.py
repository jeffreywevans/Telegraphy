"""Narrow compatibility checks for legacy `generate_story_brief` façade exports."""

from telegraphy.story_brief import cli
from telegraphy.story_brief import generate_story_brief as legacy


def test_legacy_facade_still_exposes_main_entrypoints() -> None:
    assert callable(legacy.pick_story_fields)
    assert callable(legacy.to_markdown)
    assert callable(legacy.build_auto_filename)
    assert callable(cli.main)
