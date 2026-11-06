"""Exercise real Tk layout and clipboard behavior when a display is available."""

from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from telegraphy.gui import theme
from telegraphy.gui.tablet_app import TelegraphyTablet


@pytest.fixture
def app() -> Iterator[TelegraphyTablet]:
    try:
        probe = tk.Tk()
    except tk.TclError:
        pytest.skip("A display is required for real Tk integration checks")
    probe.destroy()
    window = TelegraphyTablet()
    window.update_idletasks()
    try:
        yield window
    finally:
        window.destroy()


def test_nord_window_is_readable_at_minimum_size(app: TelegraphyTablet) -> None:
    app.geometry(f"{app._minimum_window_width()}x{app._minimum_window_height()}")
    app.update_idletasks()
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


def test_reading_pane_allows_keyboard_focus_traversal(app: TelegraphyTablet) -> None:
    event = tk.Event()
    assert app._focus_next_control(event) == "break"
    assert app._focus_previous_control(event) == "break"
