from __future__ import annotations

import json
import tkinter as tk
from unittest.mock import MagicMock

import pytest

from telegraphy.gui import runtime


def test_focus_procedures_are_loaded_when_missing() -> None:
    root = MagicMock()
    available: set[str] = set()

    def call(*args: str) -> object:
        if args[:2] == ("info", "commands"):
            return args[2] if args[2] in available else ""
        assert args[0] == "auto_load"
        available.add(args[1])
        return 1

    root.tk.call.side_effect = call
    runtime.ensure_focus_commands(root)
    assert available == {"tk_focusNext", "tk_focusPrev"}
    root.tk.call.reset_mock()
    runtime.ensure_focus_commands(root)
    assert all(call.args[0] != "auto_load" for call in root.tk.call.call_args_list)


def test_missing_focus_script_is_not_silenced() -> None:
    root = MagicMock()
    root.tk.call.return_value = ""
    with pytest.raises(tk.TclError, match="required focus procedure: tk_focusNext"):
        runtime.ensure_focus_commands(root)


def test_runtime_preflight_reports_initialization_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_initialization() -> tk.Tk:
        raise tk.TclError("cannot find init.tcl")

    monkeypatch.setattr(tk, "Tcl", fail_initialization)
    assert runtime.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["error"] == "cannot find init.tcl"
    assert "executable" in report


def test_runtime_preflight_reports_focus_loading_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = MagicMock()
    monkeypatch.setattr(tk, "Tcl", lambda: root)
    monkeypatch.setattr(runtime, "runtime_details", lambda _root: {"tk_version": "8.6"})

    def fail_loading(_root: tk.Misc) -> None:
        raise tk.TclError("cannot read focus.tcl")

    monkeypatch.setattr(runtime, "ensure_focus_commands", fail_loading)
    assert runtime.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["error"] == "cannot read focus.tcl"
    assert report["tk_version"] == "8.6"
    root.destroy.assert_called_once()
