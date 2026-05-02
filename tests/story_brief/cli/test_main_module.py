"""Tests for telegraphy.story_brief.__main__."""

from unittest.mock import patch

import pytest

from telegraphy.story_brief.__main__ import _run


def test_run_exits_with_main_return_value() -> None:
    """_run should raise SystemExit with the CLI return code."""
    with patch("telegraphy.story_brief.__main__.main", return_value=0) as mock_main:
        with pytest.raises(SystemExit) as exc_info:
            _run()

    mock_main.assert_called_once_with()
    assert exc_info.value.code == 0


def test_run_propagates_nonzero_exit() -> None:
    """_run should preserve non-zero exit codes from CLI main."""
    with patch("telegraphy.story_brief.__main__.main", return_value=1):
        with pytest.raises(SystemExit) as exc_info:
            _run()

    assert exc_info.value.code == 1
