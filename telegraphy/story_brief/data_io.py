from __future__ import annotations

import copy
import json
import os
from functools import lru_cache
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any, Final

DATA_DIR_ENV_VAR: Final = "TELEGRAPHY_DATA_DIR"
LEGACY_DATA_DIR_ENV_VAR: Final = "COMMUTED_STORY_BRIEF_DATA_DIR"

_CONFIGURED_DATA_DIR_LABEL: Final = (
    "configured data directory "
    "(TELEGRAPHY_DATA_DIR or COMMUTED_STORY_BRIEF_DATA_DIR)"
)
_PACKAGE_DATA_RESOURCE: Final = "telegraphy.story_brief.data"
_APPROVED_OVERRIDE_ROOT: Final[Path] = Path(__file__).resolve().parent / "data"


class DataDirError(ValueError):
    """Raised when the configured data directory is invalid or unreachable."""


DATA_FILENAMES: Final[dict[str, str]] = {
    "titles": "titles.json",
    "entities": "entities.json",
    "prompts": "prompts.json",
    "config": "config.json",
    "partner_distributions": "partner_distributions.json",
}

_ALLOWED_FILENAMES: Final[frozenset[str]] = frozenset(DATA_FILENAMES.values())
_HOME_MARKERS: Final[tuple[str, str]] = ("~/", "~\\")


def _is_within_allowed_root(path_text: str) -> bool:
    """Return True when path_text is within the current user's home directory."""
    allowed_root = os.path.realpath(str(Path.home()))
    candidate = os.path.realpath(path_text)
    try:
        common = os.path.commonpath([allowed_root, candidate])
    except ValueError:
        return False
    return common == allowed_root


def _selected_override_value() -> str | None:
    """Return the active override value without collapsing blank values."""
    primary_value = os.environ.get(DATA_DIR_ENV_VAR)
    if primary_value is not None:
        return primary_value
    return os.environ.get(LEGACY_DATA_DIR_ENV_VAR)


def _validate_override_text(raw_value: str) -> str:
    """Validate the override string before it is used in any path expression."""
    trimmed = raw_value.strip()
    if not trimmed:
        raise DataDirError("Configured data directory must not be empty")
    if "\x00" in trimmed:
        raise DataDirError("Configured data directory must not contain NUL bytes")
    return trimmed


def _expand_home_marker(path_text: str) -> str:
    """Expand only the current user's home marker; reject ~other forms."""
    if path_text == "~":
        return str(Path.home())
    if path_text.startswith(_HOME_MARKERS):
        return os.path.join(str(Path.home()), path_text[2:])
    if path_text.startswith("~"):
        raise DataDirError("Configured data directory must not use ~user expansion")
    return path_text


def _has_parent_traversal(path_text: str) -> bool:
    """Return True when path_text contains an explicit '..' path segment."""
    normalized = path_text.replace("\\", "/")
    return ".." in normalized.split("/")


def _validated_override_path_text(raw_value: str) -> str:
    """Return safe relative path text derived from a configured override."""
    expanded = _expand_home_marker(_validate_override_text(raw_value))
    if _has_parent_traversal(expanded):
        raise DataDirError(
            "Configured data directory must not include parent-directory traversal"
        )
    if os.path.isabs(expanded):
        raise DataDirError(
            "Configured data directory must be a relative path under the application data root"
        )
    return expanded


def _resolve_override_data_dir(raw_value: str) -> Path:
    """Resolve and validate TELEGRAPHY_DATA_DIR style overrides."""
    safe_path_text = _validated_override_path_text(raw_value)
    approved_root = _APPROVED_OVERRIDE_ROOT.resolve(strict=True)

    try:
        candidate = (approved_root / safe_path_text).resolve(strict=True)
    except OSError as exc:
        raise DataDirError(
            "Configured data directory must be an existing directory under the application data root: "
            f"{safe_path_text}"
        ) from exc

    if not candidate.is_relative_to(approved_root):
        raise DataDirError(
            "Configured data directory must stay within the application data root: "
            f"{approved_root}"
        )

    if not candidate.is_dir():
        raise DataDirError(
            "Configured data directory must be an existing directory: "
            f"{candidate}"
        )

    return candidate


def _fallback_data_dir() -> Path:
    """Return the source-tree data directory used when package resources fail."""
    return Path(__file__).resolve().parent / "data"


def resolve_data_dir() -> Path | Traversable:
    """Resolve the base directory containing story-brief data files."""
    override_raw = _selected_override_value()
    if override_raw is not None:
        return _resolve_override_data_dir(override_raw)

    try:
        return files(_PACKAGE_DATA_RESOURCE)
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        return _fallback_data_dir()


def _validate_data_filename(filename: str) -> None:
    """Reject every filename except the statically known dataset files."""
    if filename not in _ALLOWED_FILENAMES:
        raise ValueError(
            f"Refusing to open unknown data file {filename!r}. "
            f"Allowed files: {sorted(_ALLOWED_FILENAMES)}"
        )


def _contained_child_path(data_dir: Path, filename: str) -> Path:
    """Return filename under data_dir, rejecting resolved escapes and symlinks."""
    approved_root = _APPROVED_OVERRIDE_ROOT.resolve(strict=True)
    base_resolved = approved_root
    if not base_resolved.is_dir():
        raise DataDirError(
            "Configured data directory must be an existing directory: "
            f"{base_resolved}"
        )
    if not base_resolved.is_relative_to(approved_root):
        raise DataDirError(
            "Configured data directory must stay within the application data root: "
            f"{approved_root}"
        )
    target_resolved = (base_resolved / filename).resolve(strict=False)
    if not target_resolved.is_relative_to(base_resolved):
        raise DataDirError(
            f"Resolved data file path escapes the data directory: {target_resolved}"
        )
    return target_resolved


def _data_file_from_dir(data_dir: Path | Traversable, filename: str) -> Path | Traversable:
    """Return a validated dataset file path inside data_dir."""
    _validate_data_filename(filename)
    if isinstance(data_dir, Path):
        return _contained_child_path(data_dir, filename)
    return data_dir.joinpath(filename)


def _data_file(filename: str) -> Path | Traversable:
    """Return a validated path to one required story-brief data file."""
    return _data_file_from_dir(resolve_data_dir(), filename)


def _load_json(path: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
    location = "provided data directory" if data_dir is not None else _load_failure_location()
    selected_data_dir = data_dir if data_dir is not None else resolve_data_dir()
    try:
        return _load_required_dataset_files(selected_data_dir)
    except FileNotFoundError as exc:
        raise ValueError(
            f"Failed to load story brief dataset file "
            f"'{_missing_file_name(exc)}' from {location}. "
            "Verify the directory exists and contains the required JSON files."
        ) from exc
def _missing_file_name(exc: FileNotFoundError) -> str:
    if exc.filename:
        return os.path.basename(os.fsdecode(exc.filename))
    return "unknown file"


def _load_failure_location() -> str:
    if _selected_override_value() is not None:
        return _CONFIGURED_DATA_DIR_LABEL
    return "data directory"


def load_data(data_dir: Path | Traversable | None = None) -> dict[str, Any]:
    """Load the raw story dataset JSON payloads."""
    selected_data_dir = resolve_data_dir() if data_dir is None else data_dir
    try:
        return _load_required_dataset_files(selected_data_dir)
    except FileNotFoundError as exc:
        raise ValueError(
            f"Failed to load story brief dataset file "
            f"'{_missing_file_name(exc)}' from {_load_failure_location()}. "
            "Verify the directory exists and contains the required JSON files."
        ) from exc


@lru_cache(maxsize=1)
def _get_data_cached() -> dict[str, Any]:
    return load_data()


def get_data() -> dict[str, Any]:
    return copy.deepcopy(_get_data_cached())


def clear_data_cache() -> None:
    _get_data_cached.cache_clear()
