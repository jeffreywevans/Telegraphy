"""Inspect Tcl/Tk script loading and initialize keyboard navigation explicitly."""

from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path


def ensure_focus_commands(root: tk.Misc) -> None:
    """Load Tk's lazy focus procedures before UI events or test mocks can intervene."""
    for command in ("tk_focusNext", "tk_focusPrev"):
        if not root.tk.call("info", "commands", command):
            root.tk.call("auto_load", command)
        if not root.tk.call("info", "commands", command):
            raise tk.TclError(f"Tk could not load its required focus procedure: {command}")


def _read_tcl(root: tk.Misc, *args: str) -> str:
    try:
        return str(root.tk.call(*args))
    except tk.TclError as exc:
        return f"unavailable: {exc}"


def runtime_details(root: tk.Misc) -> dict[str, object]:
    """Report versions and non-secret script paths to distinguish setup from UI failures."""
    libraries = {name: _read_tcl(root, "set", name) for name in ("tcl_library", "tk_library")}
    return {
        "python": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
        "tcl_version": _read_tcl(root, "info", "patchlevel"),
        "tk_version": _read_tcl(root, "package", "provide", "Tk"),
        "libraries": libraries,
        "auto_path": _read_tcl(root, "set", "auto_path"),
        "environment": {name: os.environ.get(name) for name in ("TCL_LIBRARY", "TK_LIBRARY")},
        "scripts": {
            "init.tcl": (Path(libraries["tcl_library"]) / "init.tcl").is_file(),
            "tk.tcl": (Path(libraries["tk_library"]) / "tk.tcl").is_file(),
            "focus.tcl": (Path(libraries["tk_library"]) / "focus.tcl").is_file(),
        },
        "focus_commands": {
            command: _read_tcl(root, "info", "commands", command)
            for command in ("tk_focusNext", "tk_focusPrev")
        },
    }


def main() -> int:
    """Run a standalone CI preflight without sharing an interpreter with pytest."""
    root: tk.Tk | None = None
    cleanup: Callable[[], None] = lambda: None
    details: dict[str, object] = {
        "python": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
    }
    try:
        root = tk.Tcl()
        details.update(runtime_details(root))
        root.loadtk()
        cleanup = root.destroy
        root.withdraw()
        ensure_focus_commands(root)
        details.update(runtime_details(root))
    except tk.TclError as exc:
        if root is not None:
            details.update(runtime_details(root))
            details["tcl_error_info"] = _read_tcl(root, "set", "errorInfo")
        details["error"] = str(exc)
        print(json.dumps(details, indent=2))
        return 1
    finally:
        cleanup()
    print(json.dumps(details, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
