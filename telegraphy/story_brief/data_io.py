from __future__ import annotations

import copy
import json
import os
from functools import lru_cache
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

DATA_DIR_ENV_VAR = "TELEGRAPHY_DATA_DIR"
LEGACY_DATA_DIR_ENV_VAR = "COMMUTED_STORY_BRIEF_DATA_DIR"

DATA_FILENAMES = {
    "titles": "titles.json",
    "entities": "entities.json",
    "prompts": "prompts.json",
    "config": "config.json",
    "partner_distributions": "partner_distributions.json",
}

def _resolve_override_data_dir(raw_value: str) -> Path:
    """Resolve and validate TELEGRAPHY_DATA_DIR style overrides."""
    trimmed = raw_value.strip()
    if not trimmed:
        raise ValueError("Configured data directory must not be empty")
    if "\x00" in trimmed:
        raise ValueError("Configured data directory must not contain NUL bytes")

    # Defend against path-injection style traversal before constructing a Path.
    normalized_for_validation = trimmed.replace("\\", "/")
    segments = [part for part in normalized_for_validation.split("/") if part]
    if any(part == ".." for part in segments):
        raise ValueError(
            "Configured data directory must not include parent-directory traversal"
        )

    raw_path = Path(trimmed).expanduser()
    if not raw_path.is_absolute():
        raise ValueError("Configured data directory must be an absolute path")

    try:
        candidate = raw_path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            "Configured data directory must be an existing directory: "
            f"{raw_path}"
        ) from exc
    if not candidate.is_dir():
        raise ValueError(
            "Configured data directory must be an existing directory: "
            f"{candidate}"
        )

    return candidate


def resolve_data_dir() -> Path | Traversable:
    """Resolve the base directory containing story-brief data files."""
    override_raw = os.environ.get(DATA_DIR_ENV_VAR) or os.environ.get(
        LEGACY_DATA_DIR_ENV_VAR
    )
    if override_raw:
        return _resolve_override_data_dir(override_raw)

    repo_relative = Path(__file__).resolve().parent / "data"

    try:
        package_data = files("telegraphy.story_brief.data")
        return package_data
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        return repo_relative


def _data_file(filename: str) -> Path | Traversable:
    return resolve_data_dir().joinpath(filename)


def _load_json(path: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_data(data_dir: Path | Traversable | None = None) -> dict[str, Any]:
    """Load the raw story dataset JSON payloads."""
    try:
        if data_dir is not None:
            payloads = {
                key: _load_json(data_dir.joinpath(filename))
                for key, filename in DATA_FILENAMES.items()
            }
        else:
            payloads = {
                key: _load_json(_data_file(filename))
                for key, filename in DATA_FILENAMES.items()
            }
    except FileNotFoundError as exc:
        missing_name = Path(exc.filename).name if exc.filename else "unknown file"
        location = (
            "configured data directory (TELEGRAPHY_DATA_DIR or COMMUTED_STORY_BRIEF_DATA_DIR)"
            if os.environ.get(DATA_DIR_ENV_VAR) or os.environ.get(LEGACY_DATA_DIR_ENV_VAR)
            else "data directory"
        )
        raise ValueError(
            f"Failed to load story brief dataset file '{missing_name}' from {location}. "
            "Verify the directory exists and contains the required JSON files."
        ) from exc

    return payloads


@lru_cache(maxsize=1)
def _get_data_cached() -> dict[str, Any]:
    return load_data()


def get_data() -> dict[str, Any]:
    return copy.deepcopy(_get_data_cached())


def clear_data_cache() -> None:
    _get_data_cached.cache_clear()
