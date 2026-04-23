"""Shared pytest configuration for the test suite."""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date
from functools import lru_cache
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from commuted_calligraphy.story_brief import generate_story_brief as story_brief

_STORY_DATASET_FILES = (
    "titles.json",
    "entities.json",
    "prompts.json",
    "config.json",
    "partner_distributions.json",
)


@lru_cache(maxsize=1)
def _load_story_dataset_payloads() -> dict[str, dict[str, Any]]:
    return {
        "titles": json.loads(story_brief._data_file("titles.json").read_text(encoding="utf-8")),
        "entities": json.loads(story_brief._data_file("entities.json").read_text(encoding="utf-8")),
        "prompts": json.loads(story_brief._data_file("prompts.json").read_text(encoding="utf-8")),
        "config": json.loads(story_brief._data_file("config.json").read_text(encoding="utf-8")),
        "partner_distributions": json.loads(
            story_brief._data_file("partner_distributions.json").read_text(encoding="utf-8")
        ),
    }


@pytest.fixture
def story_dataset_payloads() -> dict[str, dict[str, Any]]:
    """Mutable copy of all JSON payloads used by schema/data tests."""
    return deepcopy(_load_story_dataset_payloads())


@pytest.fixture
def partner_character_rows() -> list[tuple[str, date, date]]:
    """Default character availability rows used by partner distribution tests."""
    return [
        ("Alex", date(2000, 1, 1), date(2000, 12, 31)),
        ("Jordan", date(2000, 1, 1), date(2000, 12, 31)),
    ]


@pytest.fixture
def partner_payload_factory() -> Callable[..., dict[str, Any]]:
    """Factory for baseline partner distribution payloads with optional era overrides."""

    def _build(
        *,
        start_date: str = "2000-01-01",
        end_date: str = "2000-12-31",
        alex_eras: list[dict[str, Any]] | None = None,
        jordan_eras: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if alex_eras is None:
            alex_eras = [
                {
                    "date_start": start_date,
                    "date_end": end_date,
                    "partners": [{"partner": "Jordan", "weight": 1.0}],
                }
            ]
        if jordan_eras is None:
            jordan_eras = [
                {
                    "date_start": start_date,
                    "date_end": end_date,
                    "partners": [{"partner": "Alex", "weight": 1.0}],
                }
            ]
        return {
            "schema_version": 1,
            "dataset_version": "test-dataset",
            "date_start": start_date,
            "date_end": end_date,
            "partner_distributions": [
                {
                    "character": "Alex",
                    "date_start": start_date,
                    "date_end": end_date,
                    "eras": alex_eras,
                },
                {
                    "character": "Jordan",
                    "date_start": start_date,
                    "date_end": end_date,
                    "eras": jordan_eras,
                },
            ],
        }

    return _build


@pytest.fixture
def source_story_data_dir() -> Path:
    """Canonical story dataset directory used by CLI/data tests."""
    return story_brief._data_file("config.json").parent


def clone_story_dataset(destination: Path, *, source_story_data_dir: Path) -> Path:
    """Copy baseline story dataset JSON files into destination and return it."""
    destination.mkdir(parents=True, exist_ok=True)
    for filename in _STORY_DATASET_FILES:
        shutil.copy2(source_story_data_dir / filename, destination / filename)
    return destination


def patch_json(path: Path, mutator: Callable[[dict[str, Any]], None]) -> None:
    """Load JSON from path, apply mutator in-place, and write updated JSON back."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@pytest.fixture
def cli_dataset_factory(tmp_path: Path, source_story_data_dir: Path) -> Callable[[str], Path]:
    """Build isolated named dataset directories cloned from canonical story data."""

    def _build(name: str) -> Path:
        return clone_story_dataset(tmp_path / name, source_story_data_dir=source_story_data_dir)

    return _build
