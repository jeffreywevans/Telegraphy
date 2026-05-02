"""Tests for telegraphy.story_brief.__main__."""

from unittest.mock import patch

import pytest

from telegraphy.story_brief.__main__ import _run


@pytest.mark.parametrize("exit_code", [0, 1])
def test_run_propagates_exit_code(exit_code: int) -> None:
    """_run should raise SystemExit with the CLI return code."""
    with patch(
        "telegraphy.story_brief.__main__.main",
        autospec=True,
        return_value=exit_code,
    ) as mock_main:
        with pytest.raises(SystemExit) as exc_info:
            _run()

    mock_main.assert_called_once_with()
    assert exc_info.value.code == exit_code
