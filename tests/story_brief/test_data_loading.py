from __future__ import annotations

import json
from pathlib import Path

import pytest

from telegraphy.story_brief import generate_story_brief as story_brief


def _write_payload(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_minimal_dataset(data_dir: Path) -> None:
    _write_payload(data_dir / "titles.json", {"titles": ["A Night in @setting"]})
    _write_payload(
        data_dir / "entities.json",
        {
            "character_availability": [
                ["Alex", "2000-01-01", "2005-12-31"],
                ["Jordan", "2000-01-01", "2005-12-31"],
            ],
            "setting_availability": [["Seattle", "2000-01-01", "2005-12-31"]],
        },
    )
    _write_payload(
        data_dir / "prompts.json",
        {
            "central_conflicts": ["Conflict"],
            "inciting_pressures": ["Pressure"],
            "ending_types": ["Open"],
            "style_guidance": ["Tight"],
            "weather": ["good"],
        },
    )
    _write_payload(
        data_dir / "config.json",
        {
            "schema_version": 1,
            "dataset_version": "test",
            "date_start": "2000-01-01",
            "date_end": "2005-12-31",
            "sexual_content_options": ["none"],
            "sexual_content_weights": [1],
            "sexual_scene_tag_groups": {
                "tone": ["tender"],
                "partner": ["married"],
            },
            "word_count_targets": [1200],
            "ordered_keys": sorted(story_brief.EXPECTED_GENERATED_FIELD_KEYS),
            "writing_preamble": "Write.",
        },
    )
    _write_payload(
        data_dir / "partner_distributions.json",
        {
            "schema_version": 1,
            "dataset_version": "test",
            "date_start": "2000-01-01",
            "date_end": "2005-12-31",
            "partner_distributions": [
                {
                    "character": "Alex",
                    "date_start": "2000-01-01",
                    "date_end": "2005-12-31",
                    "eras": [
                        {
                            "date_start": "2000-01-01",
                            "date_end": "2005-12-31",
                            "partners": [{"partner": "Jordan", "weight": 1.0}],
                        }
                    ],
                },
                {
                    "character": "Jordan",
                    "date_start": "2000-01-01",
                    "date_end": "2005-12-31",
                    "eras": [
                        {
                            "date_start": "2000-01-01",
                            "date_end": "2005-12-31",
                            "partners": [{"partner": "Alex", "weight": 1.0}],
                        }
                    ],
                },
            ],
        },
    )


def test_env_override_loads_dataset_from_custom_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "override-data"
    data_dir.mkdir()
    _write_minimal_dataset(data_dir)

    package_data_dir = Path(story_brief.__file__).resolve().parent / "data"
    assert not data_dir.resolve().is_relative_to(package_data_dir.resolve())

    monkeypatch.setenv("TELEGRAPHY_DATA_DIR", str(data_dir))
    story_brief.clear_get_data_cache()
    loaded = story_brief.load_story_data()

    assert loaded["dataset_version"] == "test"
    assert loaded["titles"] == ("A Night in @setting",)


def test_legacy_env_override_loads_dataset_from_custom_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "override-data"
    data_dir.mkdir()
    _write_minimal_dataset(data_dir)

    monkeypatch.delenv("TELEGRAPHY_DATA_DIR", raising=False)
    monkeypatch.setenv("COMMUTED_STORY_BRIEF_DATA_DIR", str(data_dir))
    story_brief.clear_get_data_cache()
    loaded = story_brief.load_story_data()

    assert loaded["dataset_version"] == "test"
    assert loaded["titles"] == ("A Night in @setting",)


def test_env_override_rejects_unresolved_title_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "override-data"
    data_dir.mkdir()
    _write_minimal_dataset(data_dir)
    _write_payload(data_dir / "titles.json", {"titles": ["Oops @protagnoist"]})

    monkeypatch.setenv("TELEGRAPHY_DATA_DIR", str(data_dir))
    story_brief.clear_get_data_cache()

    with pytest.raises(ValueError, match="unsupported token"):
        story_brief.load_story_data()


def test_load_story_data_strips_availability_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "override-data"
    data_dir.mkdir()
    _write_minimal_dataset(data_dir)
    _write_payload(
        data_dir / "entities.json",
        {
            "character_availability": [
                ["  Alex  ", "2000-01-01", "2005-12-31"],
                [" Jordan", "2000-01-01", "2005-12-31"],
            ],
            "setting_availability": [[" Seattle ", "2000-01-01", "2005-12-31"]],
        },
    )

    monkeypatch.setenv("TELEGRAPHY_DATA_DIR", str(data_dir))
    story_brief.clear_get_data_cache()
    loaded = story_brief.load_story_data()

    assert loaded["character_availability"][0][0] == "Alex"
    assert loaded["character_availability"][1][0] == "Jordan"
    assert loaded["setting_availability"][0][0] == "Seattle"


def test_env_override_requires_existing_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_dir = tmp_path / "missing"
    monkeypatch.setenv("TELEGRAPHY_DATA_DIR", str(missing_dir))
    story_brief.clear_get_data_cache()

    with pytest.raises(ValueError, match="Failed to load story brief dataset file"):
        story_brief.load_story_data()


def test_env_override_requires_absolute_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "override-data"
    data_dir.mkdir()
    _write_minimal_dataset(data_dir)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setenv("TELEGRAPHY_DATA_DIR", "override-data")
    story_brief.clear_get_data_cache()

    with pytest.raises(ValueError, match="must be an absolute path"):
        story_brief.load_story_data()


def test_get_data_returns_defensive_copies() -> None:
    story_brief.clear_get_data_cache()

    original = story_brief.get_data()
    # Top-level mutation should not poison cached state.
    original["titles"] = ("poisoned",)
    # Nested mutation should also be isolated by deepcopy.
    protagonist = next(iter(original["partner_distributions"]))
    original["partner_distributions"][protagonist][0]["poison"] = True

    reloaded = story_brief.get_data()

    assert reloaded["titles"] != ("poisoned",)
    assert "poison" not in reloaded["partner_distributions"][protagonist][0]
