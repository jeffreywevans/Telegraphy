from __future__ import annotations

import re

PROMPT_LIST_KEYS = (
    "central_conflicts",
    "inciting_pressures",
    "ending_types",
    "style_guidance",
    "weather",
)
CHARACTER_AVAILABILITY_KEY = "character_availability"
SETTING_AVAILABILITY_KEY = "setting_availability"
PARTNER_DISTRIBUTIONS_KEY = "partner_distributions"
TITLE_TOKEN_PATTERN = re.compile(r"@(?P<key>protagonist|setting|time_period)\b")
