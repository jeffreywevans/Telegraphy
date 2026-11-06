from __future__ import annotations

import pytest

from telegraphy.story_brief.normalization import _list_values


def test_list_values_rejects_non_list() -> None:
    with pytest.raises(ValueError, match="Expected a validated JSON array"):
        _list_values("not a list")
