from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path, PurePath

DEFAULT_OUTPUT_DIR = Path("output") / "story-seeds"
MAX_FILENAME_STEM_LENGTH = 120
MAX_FILENAME_BYTES = 255
SAFE_FILENAME_INPUT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,254}$")
UNSAFE_FILENAME_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]+')
PATH_SPLIT_PATTERN = re.compile(r"[\\/]+")
WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


class OutputPathError(ValueError):
    """Raised when output path resolution or validation fails."""


class OutputWriteError(RuntimeError):
    """Raised when safe output file creation/writing fails."""


def slugify(value: str) -> str:
    """Return an ASCII lowercase slug by collapsing non-alphanumerics to hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_auto_filename(title: str, today: date | datetime | str | None = None) -> str:
    """Build a sanitized default filename with a non-empty slug fallback."""
    slug = slugify(title) or "story-brief"
    if isinstance(today, str):
        date_prefix = today
    else:
        date_prefix = (today or datetime.now()).strftime("%Y-%m-%d")
    return sanitize_filename(f"{date_prefix} {slug}.md")


def _validate_user_filename_input(filename: str) -> None:
    """Validate raw user-provided filename before sanitization."""
    if not filename or filename.strip() != filename:
        raise ValueError("filename must be non-empty and must not have leading/trailing spaces")
    if "/" in filename or "\\" in filename:
        raise ValueError("filename must not contain path separators")
    if filename in {".", ".."} or ".." in filename:
        raise ValueError("filename must not contain dot-segments")
    if not SAFE_FILENAME_INPUT_PATTERN.fullmatch(filename):
        raise ValueError(
            "filename must be 1-255 characters, start with a letter or number, "
            "and contain only letters, numbers, space, dot, underscore, or hyphen"
        )


def _truncate_utf8_filename(stem: str, suffix: str, max_bytes: int = MAX_FILENAME_BYTES) -> str:
    """Return a stem+suffix pair truncated to max UTF-8 bytes."""
    if max_bytes <= 0:
        return ""

    suffix_bytes = suffix.encode("utf-8")
    max_stem_bytes = max_bytes - len(suffix_bytes)
    if max_stem_bytes <= 0:
        return suffix_bytes[:max_bytes].decode("utf-8", "ignore")

    encoded_stem = stem.encode("utf-8")
    if len(encoded_stem) > max_stem_bytes:
        stem = encoded_stem[:max_stem_bytes].decode("utf-8", "ignore")
    return f"{stem}{suffix}"


def _fallback_stem(stem: str) -> str:
    """Return a usable stem after sanitization or truncation removes all text."""
    return stem or "story-brief"


def _sanitize_stem_and_suffix(name: str) -> tuple[str, str]:
    """Sanitize stem and suffix while preserving extension shape."""
    stem, ext = os.path.splitext(name)
    safe_stem = UNSAFE_FILENAME_CHARS.sub("-", stem).rstrip(" .-")
    safe_stem = safe_stem[:MAX_FILENAME_STEM_LENGTH].rstrip(" .-")
    safe_suffix = UNSAFE_FILENAME_CHARS.sub("", ext).rstrip(" .")
    safe_suffix = _truncate_utf8_filename("", safe_suffix, MAX_FILENAME_BYTES - 1).rstrip(" .")
    return safe_stem, safe_suffix


def _apply_windows_reserved_name_guard(stem: str, suffix: str) -> tuple[str, str]:
    """Ensure stem is never a Windows reserved device name."""
    if stem.casefold() not in WINDOWS_RESERVED_NAMES:
        return stem, suffix

    candidate = _truncate_utf8_filename(f"{stem}-file", suffix, MAX_FILENAME_BYTES)
    reserved_stem, reserved_suffix = os.path.splitext(candidate)
    reserved_stem = reserved_stem.rstrip(" .-")
    if reserved_stem.casefold() in WINDOWS_RESERVED_NAMES:
        candidate = _truncate_utf8_filename("file", suffix, MAX_FILENAME_BYTES)
        reserved_stem, reserved_suffix = os.path.splitext(candidate)
        reserved_stem = _fallback_stem(reserved_stem.rstrip(" .-"))
    return reserved_stem, reserved_suffix


def _truncate_sanitized_filename(stem: str, suffix: str) -> tuple[str, str]:
    """Apply UTF-8 length limits after sanitization."""
    sanitized = _truncate_utf8_filename(stem, suffix, MAX_FILENAME_BYTES)
    truncated_stem, truncated_suffix = os.path.splitext(sanitized)
    return truncated_stem.rstrip(" .-"), truncated_suffix


def sanitize_filename(filename: str, *, suffix: str = "") -> str:
    """Sanitize filename for cross-platform safety while preserving extension."""
    raw_name = f"{filename}{suffix}" if suffix else filename
    name = PurePath(raw_name).name
    safe_stem, safe_suffix = _sanitize_stem_and_suffix(name)
    safe_stem = _fallback_stem(safe_stem)
    safe_stem, safe_suffix = _apply_windows_reserved_name_guard(safe_stem, safe_suffix)
    safe_stem, safe_suffix = _truncate_sanitized_filename(safe_stem, safe_suffix)
    safe_stem = _fallback_stem(safe_stem)
    safe_stem, safe_suffix = _truncate_sanitized_filename(safe_stem, safe_suffix)
    safe_stem, safe_suffix = _apply_windows_reserved_name_guard(safe_stem, safe_suffix)
    return f"{safe_stem}{safe_suffix}"


def _ensure_within_base(path: Path, trusted_base_dir: Path, message: str) -> None:
    """Raise OutputPathError when a resolved path escapes trusted_base_dir."""
    if not path.is_relative_to(trusted_base_dir):
        raise OutputPathError(message)


def _build_safe_relative_path(path_raw: str, *, trusted_base_dir: Path) -> Path:
    """Build a relative path from untrusted text by rejecting traversal segments."""
    trimmed = path_raw.strip()
    if not trimmed:
        return Path(".")
    if trimmed.startswith("~"):
        raise ValueError("path must not begin with '~'")

    candidate = trimmed
    if os.path.isabs(trimmed):
        normalized_base = os.path.normcase(os.path.realpath(str(trusted_base_dir)))
        normalized_candidate = os.path.normcase(os.path.realpath(trimmed))
        common_root = os.path.commonpath([normalized_base, normalized_candidate])
        if common_root != normalized_base:
            raise ValueError(
                f"absolute paths must remain inside the base directory: {normalized_base!r}"
            )
        candidate = os.path.relpath(normalized_candidate, normalized_base)

    raw_parts = [part for part in PATH_SPLIT_PATTERN.split(candidate) if part and part != "."]
    if any(part == ".." for part in raw_parts):
        raise ValueError("path must not include parent-directory traversal ('..')")
    return Path(*raw_parts) if raw_parts else Path(".")


def resolve_output_path(
    output_dir: Path,
    filename: str | None,
    generated_filename: str,
) -> Path:
    """Resolve output path and ensure it remains inside the trusted cwd."""
    trusted_base_dir = Path.cwd().resolve(strict=True)
    try:
        requested_output_dir = _build_safe_relative_path(
            str(output_dir),
            trusted_base_dir=trusted_base_dir,
        )
    except ValueError as exc:
        raise OutputPathError(f"Invalid --output-dir: {exc}") from exc

    resolved_output_dir = (trusted_base_dir / requested_output_dir).resolve(strict=False)
    _ensure_within_base(
        resolved_output_dir,
        trusted_base_dir,
        f"--output-dir must be within {trusted_base_dir}: {resolved_output_dir}",
    )

    if filename is not None:
        try:
            _validate_user_filename_input(filename)
        except ValueError as exc:
            raise OutputPathError(f"Invalid --filename: {exc}") from exc
        output_name = sanitize_filename(filename)
    else:
        output_name = generated_filename

    try:
        safe_relative_output = _build_safe_relative_path(
            str(requested_output_dir / output_name),
            trusted_base_dir=trusted_base_dir,
        )
    except ValueError as exc:
        raise OutputPathError(f"Invalid output filename/path combination: {exc}") from exc

    output_path = trusted_base_dir / safe_relative_output
    resolved_output_parent = output_path.parent.resolve(strict=False)
    candidate_output_path = resolved_output_parent / output_path.name
    _ensure_within_base(
        candidate_output_path,
        trusted_base_dir,
        "Resolved output path must be within the trusted base directory.",
    )
    return candidate_output_path


def write_output_markdown(
    output_path: Path,
    content: str,
    *,
    force: bool = False,
    trusted_base_dir: Path | None = None,
) -> None:
    """Write markdown to output_path while guarding against symlink redirection."""
    trusted_base_dir = (trusted_base_dir or Path.cwd()).resolve(strict=True)
    raw_output_path = trusted_base_dir / output_path
    resolved_parent = raw_output_path.parent.resolve(strict=False)
    candidate_output_path = resolved_parent / raw_output_path.name
    _ensure_within_base(
        candidate_output_path,
        trusted_base_dir,
        "Resolved output path must be within the trusted base directory.",
    )

    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_TRUNC if force else os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    # O_NOFOLLOW is not available on Windows. In that case we still enforce the
    # trusted base-directory boundary above, but cannot request kernel-level
    # no-symlink-follow behavior from os.open.

    try:
        fd = os.open(candidate_output_path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        raise OutputWriteError(
            "Refusing to overwrite existing file. Use --force to overwrite."
        ) from None
    except OSError as exc:
        raise OutputWriteError(f"Unable to safely open or write output path: {exc}") from exc
