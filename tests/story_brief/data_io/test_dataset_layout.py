from __future__ import annotations

import json
from pathlib import Path

import pytest

from telegraphy.story_brief import cli, data_io
from telegraphy.story_brief.dataset_layout import assemble_dataset_sections

EXPECTED_FIELD_FILES = {
    "titles.json",
    "characters.json",
    "time_period.json",
    "settings.json",
    "weather.json",
    "central_conflicts.json",
    "inciting_pressures.json",
    "ending_types.json",
    "style_guidance.json",
    "sexual_content_levels.json",
    "sexual_partners.json",
    "sexual_scene_tags.json",
    "word_count_targets.json",
    "config.json",
    "writing_preamble.json",
}


def test_packaged_dataset_has_exactly_the_independent_field_files(source_story_data_dir) -> None:
    assert {path.name for path in source_story_data_dir.glob("*.json")} == EXPECTED_FIELD_FILES
    assert set(data_io.DATA_FILENAMES.values()) == EXPECTED_FIELD_FILES


def test_config_contains_only_shared_metadata_and_output_order(source_story_data_dir) -> None:
    config = json.loads((source_story_data_dir / "config.json").read_text(encoding="utf-8"))
    assert set(config) == {"schema_version", "dataset_version", "ordered_keys"}
    characters = json.loads((source_story_data_dir / "characters.json").read_text(encoding="utf-8"))
    assert set(characters) == {"character_availability"}


@pytest.mark.parametrize("filename", sorted(EXPECTED_FIELD_FILES))
def test_each_required_file_reports_its_own_missing_filename(
    filename: str, cli_dataset_factory
) -> None:
    dataset = cli_dataset_factory("missing-field")
    (dataset / filename).unlink()
    with pytest.raises(data_io.DataDirError, match=filename):
        data_io.load_data(dataset)


@pytest.mark.parametrize("filename", sorted(EXPECTED_FIELD_FILES))
def test_each_file_rejects_non_object_json_without_a_cli_traceback(
    filename: str, cli_dataset_factory, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    dataset = cli_dataset_factory("invalid-root")
    (dataset / filename).write_text("[]", encoding="utf-8")
    monkeypatch.setenv(data_io.DATA_DIR_ENV_VAR, str(dataset))
    data_io.clear_data_cache()
    try:
        assert cli.main(["--print-only"]) == 1
        message = capsys.readouterr().err
        assert filename in message
        assert "expected a JSON object" in message
        assert "Traceback" not in message
    finally:
        data_io.clear_data_cache()


def test_fields_cannot_be_hidden_in_another_fields_file(cli_dataset_factory) -> None:
    dataset = cli_dataset_factory("wrong-field")
    config_path = dataset / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["word_count_targets"] = [500]
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match=r"config.json: unexpected keys: word_count_targets"):
        data_io.load_data(dataset)


@pytest.mark.parametrize("version", [1, 999, True, 2.0, "2", None])
def test_file_layout_rejects_unsupported_schema_versions(version, cli_dataset_factory) -> None:
    dataset = cli_dataset_factory("bad-version")
    path = dataset / "config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["schema_version"] = version
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="config.json: unsupported schema_version"):
        data_io.load_data(dataset)


def test_assembly_preserves_the_public_in_memory_sections() -> None:
    assert set(data_io.load_data()) == {
        "titles",
        "entities",
        "prompts",
        "weather",
        "config",
        "partner_distributions",
    }


def test_assembly_rejects_non_string_keys() -> None:
    with pytest.raises(ValueError, match="titles.json: object keys must be strings"):
        assemble_dataset_sections({"titles": {1: "invalid"}})


@pytest.mark.parametrize(
    ("filename", "missing_keys"),
    [
        ("titles.json", ("titles",)),
        ("time_period.json", ("date_start",)),
        ("time_period.json", ("date_start", "date_end")),
    ],
)
def test_missing_required_keys_report_filename_and_sorted_keys(
    filename: str, missing_keys: tuple[str, ...], cli_dataset_factory
) -> None:
    dataset = cli_dataset_factory("missing-required-keys")
    path = dataset / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in missing_keys:
        del payload[key]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        data_io.load_data(dataset)

    assert str(exc_info.value) == (
        f"{filename}: missing required keys: {', '.join(sorted(missing_keys))}"
    )


def test_independent_word_count_file_is_used_by_the_real_cli(
    cli_dataset_factory, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    dataset = cli_dataset_factory("word-count")
    (dataset / "word_count_targets.json").write_text(
        json.dumps({"word_count_targets": [1234]}), encoding="utf-8"
    )
    monkeypatch.setenv(data_io.DATA_DIR_ENV_VAR, str(dataset))
    data_io.clear_data_cache()
    try:
        assert cli.main(["--seed", "42", "--date", "2000-01-01", "--print-only"]) == 0
        assert "word_count_target: 1234" in capsys.readouterr().out
    finally:
        data_io.clear_data_cache()


@pytest.mark.parametrize(
    "filename", ["entities.json", "prompts.json", "partner_distributions.json"]
)
def test_old_aggregate_filenames_are_no_longer_allowed(filename: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown data file"):
        data_io._data_file_from_dir(tmp_path, filename)
