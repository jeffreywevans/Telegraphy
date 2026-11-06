from __future__ import annotations

import json
import runpy
import tkinter as tk
from pathlib import Path
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


def test_read_tcl_reports_tcl_error() -> None:
    root = MagicMock()
    root.tk.call.side_effect = tk.TclError("missing variable")

    assert runtime._read_tcl(root, "set", "missing") == "unavailable: missing variable"


def test_runtime_details_reports_versions_paths_and_focus_commands(tmp_path: Path) -> None:
    tcl_library = tmp_path / "tcl"
    tk_library = tmp_path / "tk"
    tcl_library.mkdir()
    tk_library.mkdir()
    (tcl_library / "init.tcl").write_text("", encoding="utf-8")
    (tk_library / "tk.tcl").write_text("", encoding="utf-8")
    (tk_library / "focus.tcl").write_text("", encoding="utf-8")

    root = MagicMock()
    values = {
        ("set", "tcl_library"): str(tcl_library),
        ("set", "tk_library"): str(tk_library),
        ("info", "patchlevel"): "8.6.16",
        ("package", "provide", "Tk"): "8.6.16",
        ("set", "auto_path"): str(tmp_path),
        ("info", "commands", "tk_focusNext"): "tk_focusNext",
        ("info", "commands", "tk_focusPrev"): "tk_focusPrev",
    }
    root.tk.call.side_effect = lambda *args: values[args]

    details = runtime.runtime_details(root)

    assert details["tcl_version"] == "8.6.16"
    assert details["tk_version"] == "8.6.16"
    assert details["libraries"] == {
        "tcl_library": str(tcl_library),
        "tk_library": str(tk_library),
    }
    assert details["scripts"] == {"init.tcl": True, "tk.tcl": True, "focus.tcl": True}
    assert details["focus_commands"] == {
        "tk_focusNext": "tk_focusNext",
        "tk_focusPrev": "tk_focusPrev",
    }


def test_runtime_preflight_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = MagicMock()
    monkeypatch.setattr(tk, "Tcl", lambda: root)
    monkeypatch.setattr(runtime, "runtime_details", lambda _root: {"tk_version": "8.6"})
    monkeypatch.setattr(runtime, "ensure_focus_commands", lambda _root: None)

    assert runtime.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["tk_version"] == "8.6"
    root.loadtk.assert_called_once_with()
    root.withdraw.assert_called_once_with()
    root.destroy.assert_called_once_with()


def test_runtime_module_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tk, "Tcl", MagicMock(side_effect=tk.TclError("headless")))

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(runtime.__file__), run_name="__main__")

    assert exc_info.value.code == 1


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
