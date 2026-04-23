from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from commuted_calligraphy.story_brief import generate_story_brief as story_brief
from commuted_calligraphy.story_brief.generate_story_brief import DatasetLintReport
from commuted_calligraphy.story_brief.partner_models import parse_partner_distribution_payload


def test_emit_lint_report_prints_sections(capsys: pytest.CaptureFixture[str]) -> None:
    story_brief._emit_lint_report(
        DatasetLintReport(errors=["error one"], warnings=["warn one", "warn two"])
    )

    output = capsys.readouterr().out
    assert "Dataset lint: errors" in output
    assert "- error one" in output
    assert "Dataset lint: warnings" in output
    assert "- warn one" in output
    assert "- warn two" in output


def test_emit_lint_report_prints_clean_state(capsys: pytest.CaptureFixture[str]) -> None:
    story_brief._emit_lint_report(DatasetLintReport(errors=[], warnings=[]))

    output = capsys.readouterr().out
    assert "Dataset lint: no blocking coverage gaps found." in output
    assert "Dataset lint: no warnings." in output


def test_data_file_uses_env_override_with_expanduser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "fake-home"
    override = home / "dataset"
    override.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("COMMUTED_STORY_BRIEF_DATA_DIR", "~/dataset")

    resolved = story_brief._data_file("titles.json")
    assert Path(resolved) == override / "titles.json"


def test_data_file_repo_relative_in_script_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    expected = data_dir / "titles.json"
    expected.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(story_brief, "__file__", str(tmp_path / "generate_story_brief.py"))
    monkeypatch.setattr(story_brief, "__package__", "")

    assert Path(story_brief._data_file("titles.json")) == expected


def test_data_file_falls_back_to_repo_relative_when_resources_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_relative = tmp_path / "data" / "titles.json"
    repo_relative.parent.mkdir(parents=True)

    monkeypatch.setattr(story_brief, "__file__", str(tmp_path / "generate_story_brief.py"))
    monkeypatch.setattr(story_brief, "__package__", "commuted_calligraphy.story_brief")

    def raise_missing(_package: str) -> object:
        raise ModuleNotFoundError("no package resources")

    monkeypatch.setattr(story_brief, "files", raise_missing)

    assert Path(story_brief._data_file("titles.json")) == repo_relative


def _parse_payload(payload: dict[str, object], character_rows: list[tuple[str, date, date]]) -> None:
    parse_partner_distribution_payload(
        payload,
        config_start=date(2000, 1, 1),
        config_end=date(2000, 12, 31),
        character_rows=character_rows,
        partner_distributions_key="partner_distributions",
    )


def test_partner_payload_rejects_blank_dataset_version(
    partner_payload_factory, partner_character_rows
) -> None:
    payload = partner_payload_factory()
    payload["dataset_version"] = "   "

    with pytest.raises(ValueError, match="dataset_version"):
        _parse_payload(payload, partner_character_rows)


def test_partner_payload_rejects_non_overlapping_date_range(
    partner_payload_factory, partner_character_rows
) -> None:
    payload = partner_payload_factory()
    payload["date_start"] = "1990-01-01"
    payload["date_end"] = "1990-12-31"

    with pytest.raises(ValueError, match="must overlap"):
        _parse_payload(payload, partner_character_rows)


def test_partner_payload_rejects_unknown_character(
    partner_payload_factory, partner_character_rows
) -> None:
    payload = partner_payload_factory()
    entries = list(payload["partner_distributions"])
    alex = dict(entries[0])
    alex["character"] = "Pat"
    entries[0] = alex
    payload["partner_distributions"] = entries

    with pytest.raises(ValueError, match="unknown character"):
        _parse_payload(payload, partner_character_rows)


def test_partner_payload_rejects_missing_character_coverage(
    partner_payload_factory, partner_character_rows
) -> None:
    payload = partner_payload_factory()
    payload["partner_distributions"] = [payload["partner_distributions"][0]]

    with pytest.raises(ValueError, match="missing characters"):
        _parse_payload(payload, partner_character_rows)


def test_partner_payload_rejects_partner_weight_bool(
    partner_payload_factory, partner_character_rows
) -> None:
    payload = partner_payload_factory()
    entries = list(payload["partner_distributions"])
    alex = dict(entries[0])
    eras = list(alex["eras"])
    era = dict(eras[0])
    era["partners"] = [{"partner": "Jordan", "weight": True}]
    eras[0] = era
    alex["eras"] = eras
    entries[0] = alex
    payload["partner_distributions"] = entries

    with pytest.raises(ValueError, match="weight must be a real number"):
        _parse_payload(payload, partner_character_rows)
