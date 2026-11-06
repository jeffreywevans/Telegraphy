from __future__ import annotations

import re
from datetime import date

_ISO_CALENDAR_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_ISO_CALENDAR_DATE_ERROR = "date must be an ISO calendar date (YYYY-MM-DD)"


def parse_iso_calendar_date(raw: object) -> date:
    """Parse a date written in the exact documented ``YYYY-MM-DD`` form."""
    if not isinstance(raw, str) or _ISO_CALENDAR_DATE_PATTERN.fullmatch(raw) is None:
        raise ValueError(_ISO_CALENDAR_DATE_ERROR)

    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(_ISO_CALENDAR_DATE_ERROR) from exc
