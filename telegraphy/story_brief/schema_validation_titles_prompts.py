from __future__ import annotations

import re
from typing import Any

from ._constants import PROMPT_LIST_KEYS
from .partner_models import require_keys
from .schema_validation_common import (
    validate_no_duplicate_strings,
    validate_string_list,
)

ANY_TITLE_TOKEN_PATTERN = re.compile(r"@(?P<key>[A-Za-z_]\w*)\b")
ALLOWED_TITLE_TOKENS = frozenset({"protagonist", "setting", "time_period"})
MISSING_TITLE_AT_PATTERN = re.compile(
    rf"(?<!@)\b(?P<key>{'|'.join(re.escape(t) for t in sorted(ALLOWED_TITLE_TOKENS))})\b"
)
PROMPT_LIST_KEYS_SET = frozenset(PROMPT_LIST_KEYS)
OPTIONAL_PROMPT_KEYS = frozenset({"weather_comment"})


def validate_title_tokens(values: list[str]) -> None:
    for idx, value in enumerate(values):
        for token in ANY_TITLE_TOKEN_PATTERN.findall(value):
            if token not in ALLOWED_TITLE_TOKENS:
                raise ValueError(
                    f"titles.titles[{idx}] contains unsupported token '@{token}'"
                )

        bare_tokens = sorted(
            {match.group("key") for match in MISSING_TITLE_AT_PATTERN.finditer(value)}
        )
        if bare_tokens:
            raise ValueError(
                f"titles.titles[{idx}] appears to reference token(s) without '@': "
                f"{', '.join(bare_tokens)}"
            )


def validate_prompt_lists(prompts: dict[str, Any]) -> None:
    require_keys("prompts", prompts, PROMPT_LIST_KEYS_SET)
    unexpected = sorted(set(prompts) - (PROMPT_LIST_KEYS_SET | OPTIONAL_PROMPT_KEYS))
    if unexpected:
        raise ValueError(f"prompts: unexpected keys: {', '.join(unexpected)}")
    for key in PROMPT_LIST_KEYS:
        validate_string_list("prompts", key, prompts[key])
        validate_no_duplicate_strings("prompts", key, prompts[key])
    if "weather_comment" in prompts and (
        not isinstance(prompts["weather_comment"], str) or not prompts["weather_comment"].strip()
    ):
        raise ValueError("prompts.weather_comment must be a non-empty string when provided")


def validate_titles(titles: dict[str, Any]) -> None:
    require_keys("titles", titles, {"titles"})
    validate_string_list("titles", "titles", titles["titles"])
    validate_no_duplicate_strings("titles", "titles", titles["titles"])
    validate_title_tokens(titles["titles"])
