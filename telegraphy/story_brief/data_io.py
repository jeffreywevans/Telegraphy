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


class DataDirError(ValueError):
    """Raised when the configured data directory is invalid or unreachable."""


DATA_FILENAMES = {
    "titles": "titles.json",
    "entities": "entities.json",
    "prompts": "prompts.json",
    "config": "config.json",
    "partner_distributions": "partner_distributions.json",
}

# Frozenset of the exact filenames this module is permitted to open.
_ALLOWED_FILENAMES: frozenset[str] = frozenset(DATA_FILENAMES.values())


def _resolve_override_data_dir(raw_value: str) -> Path:
    """Resolve and validate TELEGRAPHY_DATA_DIR style overrides."""
    trimmed = raw_value.strip()
    if not trimmed:
        raise DataDirError("Configured data directory must not be empty")
    if "\x00" in trimmed:
        raise DataDirError("Configured data directory must not contain NUL bytes")

    # Expand ~/ *before* traversal validation so the check runs on the real
    # path segments rather than the unexpanded string.  A value like
    # "~/../../etc" would otherwise pass the ".." check and then expand to
    # an absolute path outside any intended root.
    raw_path = Path(trimmed).expanduser()

    if not raw_path.is_absolute():
        raise DataDirError("Configured data directory must be an absolute path")

    # Validate that no parent-directory components survive after expansion.
    if ".." in raw_path.parts:
        raise DataDirError(
            "Configured data directory must not include parent-directory traversal"
        )

    try:
        candidate = raw_path.resolve(strict=True)
    except OSError as exc:
        raise DataDirError(
            "Configured data directory must be an existing directory: "
            f"{raw_path}"
        ) from exc

    if not candidate.is_dir():
        raise DataDirError(
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

    try:
        package_data = files("telegraphy.story_brief.data")
        return package_data
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        return Path(__file__).resolve().parent / "data"


def _data_file(filename: str) -> Path | Traversable:
    """Return a validated path to *filename* inside the resolved data directory.

    Two invariants are enforced here — independently of how *filename* was
    produced — so that this function is safe to call from any context:

    1. *filename* must be one of the statically known data-file names.
    2. When the data directory is a concrete ``Path``, the resulting file path
       must resolve to a location *inside* that directory (guards against any
       future caller passing an untrusted filename).
    """
    if filename not in _ALLOWED_FILENAMES:
        raise ValueError(
            f"Refusing to open unknown data file {filename!r}. "
            f"Allowed files: {sorted(_ALLOWED_FILENAMES)}"
        )

    base = resolve_data_dir()
    target = base.joinpath(filename)

    # Containment check: only meaningful (and only possible) when *base* is a
    # real filesystem Path rather than a package Traversable.
    if isinstance(base, Path):
        base_resolved = base.resolve()
        target_resolved = (base / filename).resolve()
        # Use os.path.commonpath for a prefix check that is immune to the
        # "/foo/bar".startswith("/foo/b") false-positive.
        if os.path.commonpath([base_resolved, target_resolved]) != str(base_resolved):
            raise DataDirError(
                f"Resolved data file path escapes the data directory: {target_resolved}"
            )

    return target


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
