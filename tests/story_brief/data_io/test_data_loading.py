from __future__ import annotations

import json
from pathlib import Path

import pytest

from telegraphy.story_brief import data_io, validation
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
            "sexual_scene_tag_count_weights": {"1": 1, "2": 1},
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


@pytest.fixture
def override_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "override-data"
    data_dir.mkdir()
    _write_minimal_dataset(data_dir)
    return data_dir


def test_env_override_loads_dataset_from_custom_directory(
    override_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TELEGRAPHY_DATA_DIR", str(override_data_dir))
    story_brief.clear_get_data_cache()
    loaded = story_brief.load_story_data()

    assert loaded["dataset_version"] == "test"
    assert loaded["titles"] == ("A Night in @setting",)


def test_legacy_env_override_loads_dataset_from_custom_directory(
    override_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TELEGRAPHY_DATA_DIR", raising=False)
    monkeypatch.setenv("COMMUTED_STORY_BRIEF_DATA_DIR", str(override_data_dir))
    story_brief.clear_get_data_cache()
    loaded = story_brief.load_story_data()

    assert loaded["dataset_version"] == "test"
    assert loaded["titles"] == ("A Night in @setting",)


def test_load_story_data_normalizes_sexual_scene_tag_count_weights(
    override_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_payload(
        override_data_dir / "config.json",
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
            "sexual_scene_tag_count_weights": {"2": 0.3, "1": 0.7},
            "word_count_targets": [1200],
            "ordered_keys": sorted(story_brief.EXPECTED_GENERATED_FIELD_KEYS),
            "writing_preamble": "Write.",
        },
    )
    monkeypatch.setenv("TELEGRAPHY_DATA_DIR", str(override_data_dir))
    story_brief.clear_get_data_cache()

    loaded = story_brief.load_story_data()

    assert loaded["sexual_scene_tag_count_options"] == (1, 2)
    assert loaded["sexual_scene_tag_count_weights"] == (0.7, 0.3)


def test_env_override_rejects_unresolved_title_token(
    override_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_payload(override_data_dir / "titles.json", {"titles": ["Oops @protagnoist"]})

    monkeypatch.setenv("TELEGRAPHY_DATA_DIR", str(override_data_dir))
    story_brief.clear_get_data_cache()

    with pytest.raises(ValueError, match="unsupported token"):
        story_brief.load_story_data()


def test_load_story_data_strips_availability_names(
    override_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_payload(
        override_data_dir / "entities.json",
        {
            "character_availability": [
                ["  Alex  ", "2000-01-01", "2005-12-31"],
                [" Jordan", "2000-01-01", "2005-12-31"],
            ],
            "setting_availability": [[" Seattle ", "2000-01-01", "2005-12-31"]],
        },
    )

    monkeypatch.setenv("TELEGRAPHY_DATA_DIR", str(override_data_dir))
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

    with pytest.raises(data_io.DataDirError, match="must be an existing directory"):
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

    with pytest.raises(data_io.DataDirError, match="must be an absolute path"):
        story_brief.load_story_data()


@pytest.mark.parametrize(
    ("raw_value", "message"),
    [
        ("   ", "must not be empty"),
        ("/tmp/\x00bad", "must not contain NUL bytes"),
        ("/tmp/does-not-exist*", "must be an existing directory"),
        ("/tmp/../escape", "must not include parent-directory traversal"),
    ],
)
def test_resolve_override_data_dir_rejects_invalid_values(
    raw_value: str, message: str
) -> None:
    with pytest.raises(data_io.DataDirError, match=message):
        data_io._resolve_override_data_dir(raw_value)


def test_resolve_override_data_dir_rejects_existing_file(tmp_path: Path) -> None:
    file_path = tmp_path / "not-a-dir.json"
    file_path.write_text("{}", encoding="utf-8")

    with pytest.raises(data_io.DataDirError, match="must be an existing directory"):
        data_io._resolve_override_data_dir(str(file_path))


def test_resolve_override_data_dir_accepts_spaces_and_unicode(tmp_path: Path) -> None:
    custom_data_dir = tmp_path / "Story Data 🚀"
    custom_data_dir.mkdir()

    resolved = data_io._resolve_override_data_dir(str(custom_data_dir))

    assert resolved == custom_data_dir.resolve()


def test_resolve_override_data_dir_wraps_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BrokenPath:
        def __init__(self, raw: str) -> None:
            self.raw = raw

        def is_absolute(self) -> bool:
            return True

        def resolve(self, strict: bool = False) -> Path:
            raise OSError("permission denied")

        def __str__(self) -> str:
            return self.raw

    monkeypatch.setattr(data_io, "Path", _BrokenPath)
    with pytest.raises(data_io.DataDirError, match="is unreachable or invalid"):
        data_io._resolve_override_data_dir("/restricted/path")


def test_load_data_missing_filename_without_exc_filename(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def raise_missing(_path: object) -> object:
        raise FileNotFoundError()

    monkeypatch.setattr(data_io, "_load_json", raise_missing)
    monkeypatch.delenv("TELEGRAPHY_DATA_DIR", raising=False)
    monkeypatch.delenv("COMMUTED_STORY_BRIEF_DATA_DIR", raising=False)

    with pytest.raises(ValueError, match="file 'unknown file' from data directory"):
        data_io.load_data(tmp_path)


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


def test_data_io_get_data_returns_defensive_copies() -> None:
    data_io.clear_data_cache()
    original = data_io.get_data()
    original["titles"] = {"poison": True}

    reloaded = data_io.get_data()

    assert reloaded["titles"] != {"poison": True}


def test_expected_generated_field_keys_re_export_is_immutable() -> None:
    assert isinstance(validation.EXPECTED_GENERATED_FIELD_KEYS, set)
    assert isinstance(story_brief.EXPECTED_GENERATED_FIELD_KEYS, frozenset)
    assert story_brief.EXPECTED_GENERATED_FIELD_KEYS == validation.EXPECTED_GENERATED_FIELD_KEYS
