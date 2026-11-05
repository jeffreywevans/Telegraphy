from __future__ import annotations

import argparse
from datetime import date

import pytest

from telegraphy.story_brief.availability_validation import parse_availability_boundary
from telegraphy.story_brief.cli import _parse_story_date
from telegraphy.story_brief.date_parsing import parse_iso_calendar_date
from telegraphy.story_brief.partner_models import _parse_iso_date
from telegraphy.story_brief.schema_validation_config import parse_and_validate_config_dates


def test_parse_iso_calendar_date_accepts_exact_calendar_date() -> None:
    assert parse_iso_calendar_date("2000-02-29") == date(2000, 2, 29)


@pytest.mark.parametrize(
    "raw",
    [
        "20000101",
        "2000-W01-1",
        " 2000-01-01",
        "2000-01-01 ",
    ],
)
def test_parse_iso_calendar_date_rejects_other_iso_forms(raw: str) -> None:
    with pytest.raises(ValueError, match=r"ISO calendar date \(YYYY-MM-DD\)"):
        parse_iso_calendar_date(raw)


@pytest.mark.parametrize("raw", [20000101, date(2000, 1, 1), True, None])
def test_parse_iso_calendar_date_rejects_non_strings(raw: object) -> None:
    with pytest.raises(ValueError, match=r"ISO calendar date \(YYYY-MM-DD\)"):
        parse_iso_calendar_date(raw)


def test_parse_iso_calendar_date_rejects_impossible_calendar_date() -> None:
    with pytest.raises(ValueError, match=r"ISO calendar date \(YYYY-MM-DD\)"):
        parse_iso_calendar_date("2000-02-30")


def test_cli_date_parser_rejects_compact_date() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="must be in YYYY-MM-DD format"):
        _parse_story_date("20000101")


def test_availability_date_parser_rejects_iso_week_date() -> None:
    with pytest.raises(ValueError, match=r"ISO dates \(YYYY-MM-DD\)"):
        parse_availability_boundary("2000-W01-1")


@pytest.mark.parametrize("raw", [20000101, date(2000, 1, 1)])
def test_config_date_parser_rejects_values_that_stringify_as_dates(raw: object) -> None:
    with pytest.raises(ValueError, match=r"ISO dates \(YYYY-MM-DD\)"):
        parse_and_validate_config_dates({"date_start": raw, "date_end": "2000-12-31"})


def test_partner_date_parser_uses_shared_strict_format() -> None:
    with pytest.raises(ValueError, match=r"entry.date_start must be an ISO date \(YYYY-MM-DD\)"):
        _parse_iso_date("20000101", field="entry.date_start")
