"""Exercise real Tk layout and clipboard behavior when a display is available."""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from telegraphy.gui import theme
from telegraphy.gui.models import RunOptions
from telegraphy.gui.tablet_app import EMPTY_MESSAGE, TelegraphyTablet


@pytest.fixture(scope="module")
def gui_window() -> Iterator[TelegraphyTablet]:
    """Keep one Tcl/Tk interpreter alive instead of repeatedly probing and recreating it."""
    if sys.platform not in {"win32", "darwin"} and not os.environ.get("DISPLAY"):
        pytest.skip("A display is required for real Tk integration checks")
    window = TelegraphyTablet()
    try:
        window.update()
        yield window
    finally:
        _cancel_callbacks(window)
        window.destroy()


@pytest.fixture
def app(gui_window: TelegraphyTablet) -> Iterator[TelegraphyTablet]:
    """Give each test fresh application state while retaining the native window."""
    _cancel_callbacks(gui_window)
    gui_window._worker_active = False
    gui_window.result_queue = queue.Queue()
    gui_window.run_options = RunOptions()
    gui_window.latest_output = ""
    gui_window.seed_var.set("")
    gui_window.date_var.set("")
    gui_window.generate_button.configure(state="normal")
    gui_window.copy_button.configure(state="disabled")
    gui_window.status.configure(text="Ready")
    gui_window.error_label.configure(text="")
    gui_window._set_output(EMPTY_MESSAGE)
    try:
        yield gui_window
    finally:
        gui_window._worker_active = False
        _cancel_callbacks(gui_window)


def _cancel_callbacks(window: TelegraphyTablet) -> None:
    """Prevent queued polling callbacks from leaking between tests or past root destruction."""
    for callback in window.tk.splitlist(window.tk.call("after", "info")):
        window.after_cancel(callback)


def _wait_for_geometry(window: TelegraphyTablet, width: int, height: int) -> None:
    """Process native window events before measuring the reading pane, including on Windows."""
    window.geometry(f"{width}x{height}")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        window.update()
        actual_size = (window.winfo_width(), window.winfo_height())
        if actual_size == (width, height) and window.output.winfo_viewable():
            if window.output.winfo_width() > 1 and window.output.winfo_height() > 1:
                return
        time.sleep(0.01)
    pytest.fail(
        f"Tk did not settle at {width}x{height}: window is "
        f"{window.winfo_width()}x{window.winfo_height()}, reading pane is "
        f"{window.output.winfo_width()}x{window.output.winfo_height()}"
    )


def test_nord_window_is_readable_at_minimum_size(app: TelegraphyTablet) -> None:
    _wait_for_geometry(app, app._minimum_window_width(), app._minimum_window_height())
    assert app.output.cget("background") == theme.BACKGROUND
    assert app.output.cget("state") == "disabled"
    assert app.output.winfo_width() > 400
    assert app.output.winfo_height() > 200
    assert app.copy_button.instate(["disabled"])
    assert app.generate_button.winfo_rootx() < app.copy_button.winfo_rootx()
    assert app.copy_button.winfo_rootx() + app.copy_button.winfo_width() <= (
        app.winfo_rootx() + app.winfo_width()
    )


def test_failed_generation_preserves_readable_brief_and_exact_clipboard(
    app: TelegraphyTablet,
) -> None:
    original = "---\ntitle: A signal\nprotagonist: Alex\n---\n\nKeep the ending open."
    app._worker_active = True
    app.result_queue.put(("success", original))
    app._poll_worker_queue()
    displayed = app.output.get("1.0", "end-1c")
    assert displayed.startswith("A signal")
    assert "Protagonist: Alex" in displayed
    assert app.latest_output == original
    assert app.copy_button.instate(["!disabled"])

    app._worker_active = True
    app.result_queue.put(("error", "The dataset could not be loaded."))
    app._poll_worker_queue()
    assert app.output.get("1.0", "end-1c") == displayed
    assert app.error_label.cget("text") == "The dataset could not be loaded."
    assert app.copy_button.instate(["!disabled"])
    app.copy_latest_output()
    assert app.clipboard_get() == original


def test_invalid_input_keeps_previous_result(app: TelegraphyTablet) -> None:
    app.latest_output = "previous brief"
    app._set_output("previous brief")
    app.seed_var.set("not a number")
    app.generate_story_brief()
    assert "Invalid seed" in app.error_label.cget("text")
    assert app.output.get("1.0", "end-1c") == "previous brief"
    assert not app._worker_active


def test_generating_preserves_last_result_and_copy(
    app: TelegraphyTablet,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.latest_output = "previous brief"
    app._set_output("previous brief")
    app.copy_button.configure(state="normal")
    worker = MagicMock()
    monkeypatch.setattr(threading, "Thread", worker)
    app.generate_story_brief()
    assert app.output.get("1.0", "end-1c") == "previous brief"
    assert app.latest_output == "previous brief"
    assert app.copy_button.instate(["!disabled"])
    assert app.generate_button.instate(["disabled"])
    assert app.status.cget("text") == "Generating…"
    app.generate_story_brief()
    worker.assert_called_once()
    app.result_queue.put(("error", "test completed"))
    app.update()


@pytest.mark.parametrize("copy_enabled", [False, True])
def test_reading_pane_allows_keyboard_focus_traversal(
    app: TelegraphyTablet,
    copy_enabled: bool,
) -> None:
    app.copy_button.configure(state="normal" if copy_enabled else "disabled")
    app.output.focus_force()
    app.update()
    assert app.focus_get() == app.output
    app.output.event_generate("<Tab>")
    app.update()
    assert app.focus_get() == app.input_entries[0]
    app.output.focus_force()
    app.update()
    app.output.event_generate("<Shift-Tab>")
    app.update()
    expected = app.copy_button if copy_enabled else app.generate_button
    assert app.focus_get() == expected
