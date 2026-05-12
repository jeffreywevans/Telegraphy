from __future__ import annotations

from typing import Any

from .partner_models import require_keys
from .schema_validation_common import validate_no_duplicate_strings, validate_string_list

WEATHER_REQUIRED_KEYS = frozenset({"weather"})
WEATHER_OPTIONAL_KEYS = frozenset({"weather_comment"})


def validate_weather(weather: dict[str, Any]) -> None:
    if not isinstance(weather, dict):
        raise ValueError(f"weather: expected mapping, got {type(weather).__name__}")

    require_keys("weather", weather, WEATHER_REQUIRED_KEYS)
    unexpected = sorted(set(weather) - (WEATHER_REQUIRED_KEYS | WEATHER_OPTIONAL_KEYS))
    if unexpected:
        raise ValueError(f"weather: unexpected keys: {', '.join(unexpected)}")

    validate_string_list("weather", "weather", weather["weather"])
    validate_no_duplicate_strings("weather", "weather", weather["weather"])

    if "weather_comment" in weather and (
        not isinstance(weather["weather_comment"], str)
        or not weather["weather_comment"].strip()
    ):
        raise ValueError("weather.weather_comment must be a non-empty string when provided")
