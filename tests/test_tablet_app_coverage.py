from __future__ import annotations

import queue
import runpy
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError
from tkinter import font as tkfont
from tkinter import ttk
from unittest.mock import MagicMock, call

import pytest

from telegraphy.gui import tablet_app
from telegraphy.gui.cli_runner import CliRunResult
from telegraphy.gui.models import RunOptions


class _FakeWidget:
    """Minimal dynamic-free stand-in for the Tk widgets built by the GUI."""

    def __init__(self, *, bg: object = None) -> None:
        self._bg = bg
        self.pack = MagicMock()
        self.bind = MagicMock()
        self.configure = MagicMock()
        self.grid = MagicMock()
        self.create_window = MagicMock(return_value=111)
        self.create_oval = MagicMock()
        self.create_polygon = MagicMock(return_value=321)
        self.coords = MagicMock()
        self.itemconfigure = MagicMock()
        self.tag_lower = MagicMock()
        self.yview = MagicMock()
        self.delete = MagicMock()
        self.insert = MagicMock()
        self.see = MagicMock()
        self.set = MagicMock()

    def cget(self, key: str) -> object:
        if key == "bg":
            return self._bg
        raise KeyError(key)


class _FakeStringVar(tk.StringVar):
    """Root-free StringVar implementation for tests that bypass Tk startup."""

    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


def test_read_app_version_falls_back_when_package_metadata_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_version(distribution_name: str) -> str:
        assert distribution_name == "Commuted_Telegraphy"
        raise PackageNotFoundError(distribution_name)

    monkeypatch.setattr(tablet_app, "version", missing_version)

    assert tablet_app._read_app_version() == "development"


def _make_tablet() -> tablet_app.TelegraphyTablet:
    return tablet_app.TelegraphyTablet.__new__(tablet_app.TelegraphyTablet)


def test_init_and_configure_style_and_build(monkeypatch: pytest.MonkeyPatch) -> None:
    tablet = _make_tablet()

    monkeypatch.setattr(tk.Tk, "__init__", lambda self: None)
    monkeypatch.setattr(tablet, "title", lambda _title: None)
    monkeypatch.setattr(tablet, "geometry", lambda _geometry: None)
    monkeypatch.setattr(tablet, "minsize", lambda _w, _h: None)
    monkeypatch.setattr(tablet, "configure", lambda **_kwargs: None)

    monkeypatch.setattr(tablet, "_select_display_font", lambda: "Chosen Font")

    style = MagicMock()
    monkeypatch.setattr(ttk, "Style", lambda _parent: style)

    def make_widget(*_args: object, **kwargs: object) -> _FakeWidget:
        return _FakeWidget(bg=kwargs.get("bg"))

    canvas = make_widget()
    text = make_widget()
    text_options: dict[str, object] = {}
    button = make_widget()
    status = make_widget()
    scrollbar = make_widget()

    monkeypatch.setattr(tk, "Canvas", lambda *_args, **_kwargs: canvas)
    monkeypatch.setattr(tk, "Frame", make_widget)
    monkeypatch.setattr(tk, "Label", make_widget)

    def make_text(*_args: object, **kwargs: object) -> _FakeWidget:
        text_options.update(kwargs)
        return text

    monkeypatch.setattr(tk, "Text", make_text)
    monkeypatch.setattr(ttk, "Button", lambda *_args, **_kwargs: button)
    monkeypatch.setattr(ttk, "Label", lambda *_args, **_kwargs: status)
    monkeypatch.setattr(ttk, "Scrollbar", lambda *_args, **_kwargs: scrollbar)
    monkeypatch.setattr(ttk, "Entry", make_widget)
    monkeypatch.setattr(tk, "StringVar", _FakeStringVar)

    poll_calls: list[tuple[int, Callable[[], object]]] = []
    monkeypatch.setattr(tablet, "after", lambda delay, fn: poll_calls.append((delay, fn)))

    tablet_app.TelegraphyTablet.__init__(tablet, RunOptions(seed=123, date="2000-01-01"))

    assert tablet.latest_output == ""
    assert tablet.seed_var.get() == "123"
    assert tablet.date_var.get() == "2000-01-01"
    assert isinstance(tablet.result_queue, queue.Queue)
    assert text_options["font"] == ("Chosen Font", 11)
    style.theme_use.assert_called_once_with("clam")
    assert style.configure.call_args_list == [
        call(
            tablet_app.TABLET_BUTTON_STYLE,
            font=(tablet.font_family, 14, "bold"),
            padding=(18, 12),
        ),
        call(
            "Status.TLabel",
            background=tablet_app.TABLET_INNER_SECTION_COLOR,
            foreground="#d1d5db",
            font=(tablet.font_family, 10),
        ),
    ]
    assert poll_calls == []


def test_generate_story_brief_starts_worker_and_starts_polling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tablet = _make_tablet()
    tablet.generate_button = MagicMock()
    tablet.copy_button = MagicMock()
    tablet.status = MagicMock()
    tablet.run_options = RunOptions()
    tablet.seed_var = _FakeStringVar()
    tablet.date_var = _FakeStringVar()

    set_output = MagicMock()
    monkeypatch.setattr(tablet, "_set_output", set_output)

    poll_called: list[bool] = []
    monkeypatch.setattr(tablet, "_poll_worker_queue", lambda: poll_called.append(True))

    thread_record: dict[str, object] = {}

    class FakeThread:
        def __init__(self, *, target: Callable[[], None], daemon: bool) -> None:
            thread_record["target"] = target
            thread_record["daemon"] = daemon

        def start(self) -> None:
            thread_record["started"] = True

    monkeypatch.setattr(threading, "Thread", FakeThread)

    tablet.generate_story_brief()

    tablet.generate_button.configure.assert_called_once_with(state="disabled")
    tablet.copy_button.configure.assert_called_once_with(state="disabled")
    tablet.status.configure.assert_called_once_with(text="Generating...")
    set_output.assert_called_once_with("Kendall is warming her sweet ass up...")
    assert thread_record == {"target": tablet._run_cli_worker, "daemon": True, "started": True}
    assert tablet._worker_active is True
    assert poll_called == [True]


def test_generate_story_brief_invalid_seed_polls_once_but_does_not_start_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tablet = _make_tablet()
    tablet.generate_button = MagicMock()
    tablet.copy_button = MagicMock()
    tablet.status = MagicMock()
    tablet.run_options = RunOptions()
    tablet.result_queue = queue.Queue[tuple[str, str]]()
    tablet.seed_var = _FakeStringVar("bad")
    tablet.date_var = _FakeStringVar()

    poll_called: list[bool] = []
    monkeypatch.setattr(tablet, "_poll_worker_queue", lambda: poll_called.append(True))

    thread_called: list[bool] = []

    class FakeThread:
        def __init__(self, **_kwargs: object) -> None:
            thread_called.append(True)

        def start(self) -> None:
            thread_called.append(True)

    monkeypatch.setattr(threading, "Thread", FakeThread)

    tablet.generate_story_brief()

    assert poll_called == [True]
    assert not thread_called
    assert tablet._worker_active is True
    assert tablet.generate_button.configure.call_args_list == [call(state="disabled")]
    assert tablet.result_queue.get_nowait()[0] == "error"


def test_generate_story_brief_invalid_seed_queue_message_is_consumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tablet = _make_tablet()
    tablet.result_queue = queue.Queue[tuple[str, str]]()
    tablet.generate_button = MagicMock()
    tablet.copy_button = MagicMock()
    tablet.status = MagicMock()
    tablet.output = MagicMock()
    tablet.run_options = RunOptions()
    tablet.seed_var = _FakeStringVar("bad")
    tablet.date_var = _FakeStringVar()

    after_calls: list[tuple[int, object]] = []
    monkeypatch.setattr(tablet, "after", lambda delay, fn: after_calls.append((delay, fn)))

    output_messages: list[str] = []
    monkeypatch.setattr(tablet, "_set_output", lambda msg: output_messages.append(msg))

    thread_called: list[bool] = []

    class FakeThread:
        def __init__(self, **_kwargs: object) -> None:
            thread_called.append(True)

        def start(self) -> None:
            thread_called.append(True)

    monkeypatch.setattr(threading, "Thread", FakeThread)

    tablet.generate_story_brief()

    assert not thread_called
    assert tablet._worker_active is False
    assert tablet.generate_button.configure.call_args_list[-1] == call(state="normal")
    assert tablet.copy_button.configure.call_args_list[0] == call(state="disabled")
    assert after_calls == []

    assert tablet.result_queue.empty()
    assert "Invalid seed" in output_messages[-1]
    tablet.status.configure.assert_called_with(text="Generation failed.")
    assert tablet.generate_button.configure.call_args_list[-1] == call(state="normal")
    assert tablet.copy_button.configure.call_args_list[-1] == call(state="disabled")


def test_resolve_run_options_invalid_seed() -> None:
    tablet = _make_tablet()
    tablet.result_queue = queue.Queue[tuple[str, str]]()
    tablet.run_options = RunOptions()
    tablet.seed_var = _FakeStringVar("oops")
    tablet.date_var = _FakeStringVar()

    assert tablet._resolve_run_options() is None
    status, message = tablet.result_queue.get_nowait()
    assert status == "error"
    assert "Invalid seed" in message


def test_resolve_run_options_preserves_startup_seed_and_date_when_blank() -> None:
    tablet = _make_tablet()
    tablet.run_options = RunOptions(seed=7, date="2000-02-03", timeout_seconds=9.0)
    tablet.seed_var = _FakeStringVar()
    tablet.date_var = _FakeStringVar()

    resolved = tablet._resolve_run_options()

    assert resolved == RunOptions(seed=7, date="2000-02-03", timeout_seconds=9.0)


def test_run_cli_worker_success_error_and_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    tablet = _make_tablet()
    tablet.result_queue = queue.Queue[tuple[str, str]]()
    tablet.run_options = RunOptions(timeout_seconds=1.5)
    monkeypatch.setattr(
        tablet_app,
        "run_story_brief_cli",
        lambda _options: CliRunResult(status="success", message="done"),
    )
    tablet._run_cli_worker()
    assert tablet.result_queue.get_nowait() == ("success", "done")

    monkeypatch.setattr(
        tablet_app,
        "run_story_brief_cli",
        lambda _options: CliRunResult(status="error", message="err"),
    )
    tablet._run_cli_worker()
    assert tablet.result_queue.get_nowait() == ("error", "err")

    def raise_unexpected(_options: RunOptions) -> CliRunResult:
        raise RuntimeError("worker crashed")

    monkeypatch.setattr(tablet_app, "run_story_brief_cli", raise_unexpected)
    tablet._run_cli_worker()
    assert tablet.result_queue.get_nowait() == (
        "error",
        "Unexpected CLI worker failure: worker crashed",
    )


def test_poll_queue_and_copy_and_output_and_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    tablet = _make_tablet()
    tablet.result_queue = queue.Queue[tuple[str, str]]()
    tablet.generate_button = MagicMock()
    tablet.copy_button = MagicMock()
    tablet.status = MagicMock()
    tablet.output = MagicMock()
    tablet.canvas = MagicMock()
    tablet.canvas.create_polygon.return_value = 999
    tablet.screen_window = 7
    tablet.latest_output = ""

    after_calls: list[tuple[int, Callable[[], object]]] = []
    monkeypatch.setattr(tablet, "after", lambda delay, fn: after_calls.append((delay, fn)))

    output_messages: list[str] = []
    monkeypatch.setattr(tablet, "_set_output", output_messages.append)

    tablet._worker_active = True
    tablet._poll_worker_queue()

    tablet.result_queue.put(("success", "hello world"))
    tablet._poll_worker_queue()
    assert tablet.latest_output == "hello world"
    assert output_messages[-1] == "hello world"
    tablet.status.configure.assert_called_with(text="Generated. Ready to copy.")
    assert tablet.copy_button.configure.call_args_list[-1] == call(state="normal")
    assert tablet._worker_active is False

    tablet._worker_active = True
    tablet.result_queue.put(("error", "bad"))
    tablet._poll_worker_queue()
    assert tablet.latest_output == ""
    assert output_messages[-1] == "bad"
    tablet.status.configure.assert_called_with(text="Generation failed.")
    assert tablet.copy_button.configure.call_args_list[-1] == call(state="disabled")

    tablet._worker_active = True
    tablet.result_queue.put(("success", ""))
    tablet._poll_worker_queue()
    assert tablet.latest_output == ""
    assert output_messages[-1] == ""
    tablet.status.configure.assert_called_with(text="No output generated.")
    assert tablet.copy_button.configure.call_args_list[-1] == call(state="disabled")

    tablet.copy_latest_output()
    tablet.status.configure.assert_called_with(text="Nothing to copy yet.")

    clipboard_clear = MagicMock()
    clipboard_append = MagicMock()
    update_idletasks = MagicMock()
    monkeypatch.setattr(tablet, "clipboard_clear", clipboard_clear)
    monkeypatch.setattr(tablet, "clipboard_append", clipboard_append)
    monkeypatch.setattr(tablet, "update_idletasks", update_idletasks)

    tablet.latest_output = "copy me"
    tablet.copy_latest_output()
    clipboard_clear.assert_called_once_with()
    clipboard_append.assert_called_once_with("copy me")
    update_idletasks.assert_called_once_with()
    tablet.status.configure.assert_called_with(text="Copied to clipboard.")


def test_pixels_per_inch_falls_back_and_caches_after_tcl_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tablet = _make_tablet()
    tablet._dpi_cache = None

    mock_fpixels = MagicMock(side_effect=tk.TclError("boom"))
    monkeypatch.setattr(tablet, "winfo_fpixels", mock_fpixels)
    assert tablet._pixels_per_inch() == tablet_app.DEFAULT_DPI
    assert tablet._pixels_per_inch() == tablet_app.DEFAULT_DPI
    mock_fpixels.assert_called_once_with("1i")


def test_set_output_updates_text_widget_state() -> None:
    tablet = _make_tablet()
    tablet.output = MagicMock()

    tablet_app.TelegraphyTablet._set_output(tablet, "render")
    assert tablet.output.configure.call_args_list[:1] == [call(state="normal")]
    tablet.output.delete.assert_called_once_with("1.0", "end")
    tablet.output.insert.assert_called_once_with("1.0", "render")
    assert tablet.output.configure.call_args_list[-1] == call(state="disabled")
    tablet.output.see.assert_called_once_with("1.0")


def test_redraw_tablet_updates_canvas_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    tablet = _make_tablet()
    tablet.canvas = MagicMock()
    tablet.screen_window = 7

    event = tk.Event()
    event.width = 500
    event.height = 300
    rr_calls: list[tuple[float, ...]] = []

    def record_rounded_rectangle(
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        radius: float,
        fill: str,
        outline: str,
        width: int,
        tags: str,
    ) -> None:
        rr_calls.append((x1, y1, x2, y2, radius, width))

    monkeypatch.setattr(tablet, "_rounded_rectangle", record_rounded_rectangle)
    tablet._redraw_tablet(event)
    assert len(rr_calls) == 2
    tablet.canvas.delete.assert_called_once_with("tablet")
    tablet.canvas.coords.assert_called_once_with(7, 40, 40)
    tablet.canvas.itemconfigure.assert_called_once_with(7, width=420, height=220)


def test_rounded_rectangle_creates_polygon() -> None:
    tablet = _make_tablet()
    tablet.canvas = MagicMock()

    tablet_app.TelegraphyTablet._rounded_rectangle(
        tablet,
        x1=0,
        y1=0,
        x2=10,
        y2=10,
        radius=1,
        fill="f",
        outline="o",
        width=2,
        tags="t",
    )
    tablet.canvas.create_polygon.assert_called_once()


def test_font_selection_by_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    tablet = _make_tablet()

    monkeypatch.setattr(tkfont, "families", lambda _root: ("Aptos Serif", "Segoe UI"))
    monkeypatch.setattr(sys, "platform", "win32")
    assert tablet._select_display_font() == "Aptos Serif"

    monkeypatch.setattr(tkfont, "families", lambda _root: ("Ubuntu",))
    monkeypatch.setattr(sys, "platform", "linux")
    assert tablet._select_display_font() == "Ubuntu"

    monkeypatch.setattr(tkfont, "families", lambda _root: (".AppleSystemUIFont",))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert tablet._select_display_font() == ".AppleSystemUIFont"

    monkeypatch.setattr(tkfont, "families", lambda _root: ("Monospace",))
    monkeypatch.setattr(sys, "platform", "freebsd13")
    assert tablet._select_display_font() == tablet_app.DEFAULT_FONT_FAMILY


def test_font_fallback_helpers() -> None:
    assert (
        tablet_app.TelegraphyTablet._pick_first_available_font(
            ("One", "Two", "Three"),
            {"zero", "three"},
        )
        == "Three"
    )

    assert (
        tablet_app.TelegraphyTablet._pick_first_available_font(
            ("One", "Two", "Three"),
            {"zero"},
        )
        == "One"
    )

    assert (
        tablet_app.TelegraphyTablet._pick_first_available_font((), set())
        == tablet_app.DEFAULT_FONT_FAMILY
    )


def test_main_invokes_mainloop(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    class FakeTablet:
        def __init__(self, run_options: RunOptions) -> None:
            called.append(str(run_options.seed))

        def mainloop(self) -> None:
            called.append("loop")

    monkeypatch.setattr(tablet_app, "TelegraphyTablet", FakeTablet)
    assert tablet_app.main(["--seed", "7"]) == 0
    assert called == ["7", "loop"]


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf", "-inf", "not-a-number"])
def test_gui_parser_rejects_non_positive_or_non_finite_timeout(timeout: str) -> None:
    parser = tablet_app._build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--timeout", timeout])

    assert exc_info.value.code == 2


def test_gui_parser_accepts_positive_finite_timeout() -> None:
    args = tablet_app._build_parser().parse_args(["--timeout", "0.25"])

    assert args.timeout == 0.25


def test_main_headless_tcl_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeTablet:
        def __init__(self, run_options: RunOptions) -> None:
            raise tk.TclError("no display")

    monkeypatch.setattr(tablet_app, "TelegraphyTablet", FakeTablet)
    assert tablet_app.main([]) == 1
    assert "headless mode detected" in capsys.readouterr().err.lower()


def test_module_entrypoint_raises_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force a TclError to ensure the test is deterministic and doesn't hang on GUI systems.
    monkeypatch.setattr(
        tk.Tk,
        "__init__",
        MagicMock(side_effect=tk.TclError("headless")),
    )
    monkeypatch.setattr(sys, "argv", [str(tablet_app.__file__)])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(tablet_app.__file__), run_name="__main__")

    assert exc_info.value.code == 1
