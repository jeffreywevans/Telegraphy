from __future__ import annotations

from datetime import date
from io import StringIO
from pathlib import Path
from typing import Callable

import pytest

from telegraphy.story_brief import data_io
from telegraphy.story_brief import generate_story_brief as story_brief
from telegraphy.story_brief.linting import DatasetLintReport
from telegraphy.story_brief.partner_models import parse_partner_distribution_payload


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


def test_emit_lint_report_accepts_explicit_file_stream() -> None:
    out = StringIO()

    story_brief._emit_lint_report(
        DatasetLintReport(errors=["error one"], warnings=["warn one"]), file=out
    )

    output = out.getvalue()
    assert "Dataset lint: errors" in output
    assert "- error one" in output
    assert "Dataset lint: warnings" in output
    assert "- warn one" in output


def test_data_file_uses_env_override_with_expanduser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "fake-home"
    override = home / "dataset"
    override.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TELEGRAPHY_DATA_DIR", "~/dataset")

    resolved = data_io._data_file("titles.json")
    assert Path(resolved) == override / "titles.json"


def test_data_file_repo_relative_when_resources_are_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    expected = data_dir / "titles.json"
    expected.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(data_io, "__file__", str(tmp_path / "data_io.py"))
    monkeypatch.setattr(data_io, "__package__", "telegraphy.story_brief")

    def raise_missing(_package: str) -> object:
        raise ModuleNotFoundError("no package resources")

    monkeypatch.setattr(data_io, "files", raise_missing)

    assert Path(data_io._data_file("titles.json")) == expected


def test_data_file_falls_back_to_repo_relative_when_resources_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_relative = tmp_path / "data" / "titles.json"
    repo_relative.parent.mkdir(parents=True)

    monkeypatch.setattr(data_io, "__file__", str(tmp_path / "data_io.py"))
    monkeypatch.setattr(data_io, "__package__", "telegraphy.story_brief")

    def raise_missing(_package: str) -> object:
        raise ModuleNotFoundError("no package resources")

    monkeypatch.setattr(data_io, "files", raise_missing)

    assert Path(data_io._data_file("titles.json")) == repo_relative


@pytest.mark.parametrize(
    "error",
    [FileNotFoundError("missing package data"), TypeError("invalid package type")],
)
def test_data_file_repo_relative_fallback_for_resource_resolution_errors(
    error: Exception, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = tmp_path / "data" / "titles.json"
    expected.parent.mkdir(parents=True)
    expected.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(data_io, "__file__", str(tmp_path / "data_io.py"))
    monkeypatch.setattr(data_io, "__package__", "telegraphy.story_brief")

    def raise_error(_package: str) -> object:
        raise error

    monkeypatch.setattr(data_io, "files", raise_error)

    assert Path(data_io._data_file("titles.json")) == expected


def _parse_payload(
    payload: dict[str, object], character_rows: list[tuple[str, date, date]]
) -> None:
    parse_partner_distribution_payload(
        payload,
        config_start=date(2000, 1, 1),
        config_end=date(2000, 12, 31),
        character_rows=character_rows,
        partner_distributions_key="partner_distributions",
    )


def _mutate_blank_dataset_version(payload: dict[str, object]) -> None:
    payload["dataset_version"] = "   "


def _mutate_non_overlapping_date_range(payload: dict[str, object]) -> None:
    payload["date_start"] = "1990-01-01"
    payload["date_end"] = "1990-12-31"


def _mutate_unknown_character(payload: dict[str, object]) -> None:
    payload["partner_distributions"][0]["character"] = "Pat"


def _mutate_missing_character_coverage(payload: dict[str, object]) -> None:
    payload["partner_distributions"] = [payload["partner_distributions"][0]]


def _mutate_partner_weight_bool(payload: dict[str, object]) -> None:
    payload["partner_distributions"][0]["eras"][0]["partners"] = [
        {"partner": "Jordan", "weight": True}
    ]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (_mutate_blank_dataset_version, "dataset_version"),
        (_mutate_non_overlapping_date_range, "must overlap"),
        (_mutate_unknown_character, "unknown character"),
        (_mutate_missing_character_coverage, "missing characters"),
        (_mutate_partner_weight_bool, "weight must be a real number"),
    ],
)
def test_partner_payload_validation_error_cases_are_parameterized(
    mutator: Callable[[dict[str, object]], None],
    message: str,
    partner_payload_factory,
    partner_character_rows,
) -> None:
    payload = partner_payload_factory()
    mutator(payload)

    with pytest.raises(ValueError, match=message):
        _parse_payload(payload, partner_character_rows)
