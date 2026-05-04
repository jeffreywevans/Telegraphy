from __future__ import annotations

import queue
from types import SimpleNamespace
from unittest.mock import MagicMock, call

from telegraphy.gui import tablet_app


def _make_tablet() -> tablet_app.TelegraphyTablet:
    return tablet_app.TelegraphyTablet.__new__(tablet_app.TelegraphyTablet)


def test_init_and_configure_style_and_build(monkeypatch):
    tablet = _make_tablet()

    monkeypatch.setattr(tablet_app.tk.Tk, "__init__", lambda self: None)
    monkeypatch.setattr(tablet, "title", lambda _title: None)
    monkeypatch.setattr(tablet, "geometry", lambda _geometry: None)
    monkeypatch.setattr(tablet, "minsize", lambda _w, _h: None)
    monkeypatch.setattr(tablet, "configure", lambda **_kwargs: None)

    monkeypatch.setattr(tablet, "_select_display_font", lambda: "Chosen Font")

    style = MagicMock()
    monkeypatch.setattr(tablet_app.ttk, "Style", lambda _parent: style)

    class FakeWidget(SimpleNamespace):
        def __init__(self):
            super().__init__(
                pack=MagicMock(),
                bind=MagicMock(),
                configure=MagicMock(),
                grid=MagicMock(),
                _bg=None,
            )

        def cget(self, key):
            if key == "bg":
                return self._bg
            raise KeyError(key)

    def make_widget(**kwargs) -> FakeWidget:
        widget = FakeWidget()
        widget._bg = kwargs.get("bg")
        return widget
    canvas = make_widget()
    canvas.create_window = MagicMock(return_value=111)
    canvas.create_oval = MagicMock()
    canvas.create_polygon = MagicMock(return_value=321)
    canvas.coords = MagicMock()
    canvas.itemconfigure = MagicMock()
    canvas.tag_lower = MagicMock()

    text = make_widget()
    text.yview = MagicMock()
    text.delete = MagicMock()
    text.insert = MagicMock()
    text.see = MagicMock()
    text._bg = None
    button = make_widget()
    status = make_widget()
    scrollbar = make_widget()
    scrollbar.set = MagicMock()

    monkeypatch.setattr(tablet_app.tk, "Canvas", lambda *args, **kwargs: canvas)
    monkeypatch.setattr(tablet_app.tk, "Frame", lambda *args, **kwargs: make_widget(**kwargs))
    monkeypatch.setattr(tablet_app.tk, "Label", lambda *args, **kwargs: make_widget(**kwargs))
    monkeypatch.setattr(tablet_app.tk, "Text", lambda *args, **kwargs: text)
    monkeypatch.setattr(tablet_app.ttk, "Button", lambda *args, **kwargs: button)
    monkeypatch.setattr(tablet_app.ttk, "Label", lambda *args, **kwargs: status)
    monkeypatch.setattr(tablet_app.ttk, "Scrollbar", lambda *args, **kwargs: scrollbar)
    monkeypatch.setattr(tablet_app.ttk, "Entry", lambda *args, **kwargs: make_widget())

    class FakeStringVar:
        def __init__(self, value=""):
            self._value = value

        def get(self):
            return self._value

        def set(self, value):
            self._value = value

    monkeypatch.setattr(tablet_app.tk, "StringVar", FakeStringVar)

    poll_calls: list[tuple[int, object]] = []
    monkeypatch.setattr(tablet, "after", lambda delay, fn: poll_calls.append((delay, fn)))

    tablet.__init__(tablet_app.RunOptions(seed=123, date="2000-01-01"))

    assert tablet.latest_output == ""
    assert tablet.seed_var.get() == "123"
    assert tablet.date_var.get() == "2000-01-01"
    assert isinstance(tablet.result_queue, queue.Queue)
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
    assert poll_calls[-1] == (100, tablet._poll_worker_queue)


def test_decode_output_paths(monkeypatch):
    tablet = _make_tablet()

    monkeypatch.setattr(tablet_app, "getpreferredencoding", lambda _flag: "utf-8")
    assert tablet._decode_output("ok".encode("utf-8")) == "ok"

    monkeypatch.setattr(tablet_app, "getpreferredencoding", lambda _flag: "bad-encoding")
    assert "�" in tablet._decode_output(b"\xff")

    monkeypatch.setattr(tablet_app, "getpreferredencoding", lambda _flag: "")
    assert tablet._decode_output(b"fallback") == "fallback"


def test_generate_story_brief_starts_worker(monkeypatch):
    tablet = _make_tablet()
    tablet.generate_button = MagicMock()
    tablet.copy_button = MagicMock()
    tablet.status = MagicMock()
    tablet.run_options = tablet_app.RunOptions()
    tablet.seed_var = SimpleNamespace(get=lambda: "")
    tablet.date_var = SimpleNamespace(get=lambda: "")

    monkeypatch.setattr(tablet, "_set_output", MagicMock())

    thread_record: dict[str, object] = {}

    class FakeThread:
        def __init__(self, *, target, daemon):
            thread_record["target"] = target
            thread_record["daemon"] = daemon

        def start(self):
            thread_record["started"] = True

    monkeypatch.setattr(tablet_app.threading, "Thread", FakeThread)

    tablet.generate_story_brief()

    tablet.generate_button.configure.assert_called_once_with(state="disabled")
    tablet.copy_button.configure.assert_called_once_with(state="disabled")
    tablet.status.configure.assert_called_once_with(text="Generating...")
    tablet._set_output.assert_called_once_with("Kendall is warming her sweet ass up...")
    assert thread_record == {"target": tablet._run_cli_worker, "daemon": True, "started": True}




def test_generate_story_brief_invalid_seed_does_not_start_poll_or_worker(monkeypatch):
    tablet = _make_tablet()
    tablet.generate_button = MagicMock()
    tablet.copy_button = MagicMock()
    tablet.status = MagicMock()
    tablet.run_options = tablet_app.RunOptions()
    tablet.result_queue = queue.Queue()
    tablet.seed_var = SimpleNamespace(get=lambda: "bad")
    tablet.date_var = SimpleNamespace(get=lambda: "")

    poll_called: list[bool] = []
    monkeypatch.setattr(tablet, "_poll_worker_queue", lambda: poll_called.append(True))

    thread_called: list[bool] = []

    class FakeThread:
        def __init__(self, **_kwargs):
            thread_called.append(True)

        def start(self):
            thread_called.append(True)

    monkeypatch.setattr(tablet_app.threading, "Thread", FakeThread)

    tablet.generate_story_brief()

    assert not poll_called
    assert not thread_called
    tablet.status.configure.assert_called_once_with(text="Generation failed.")
    assert tablet.result_queue.get_nowait()[0] == "error"

def test_resolve_run_options_invalid_seed(monkeypatch):
    tablet = _make_tablet()
    tablet.result_queue = queue.Queue()
    tablet.run_options = tablet_app.RunOptions()
    tablet.seed_var = SimpleNamespace(get=lambda: "oops")
    tablet.date_var = SimpleNamespace(get=lambda: "")

    assert tablet._resolve_run_options() is None
    status, message = tablet.result_queue.get_nowait()
    assert status == "error"
    assert "Invalid seed" in message




def test_resolve_run_options_preserves_startup_seed_and_date_when_blank():
    tablet = _make_tablet()
    tablet.run_options = tablet_app.RunOptions(seed=7, date="2000-02-03", timeout_seconds=9.0)
    tablet.seed_var = SimpleNamespace(get=lambda: "")
    tablet.date_var = SimpleNamespace(get=lambda: "")

    resolved = tablet._resolve_run_options()

    assert resolved == tablet_app.RunOptions(seed=7, date="2000-02-03", timeout_seconds=9.0)

def test_run_cli_worker_success_error_and_exception(monkeypatch):
    tablet = _make_tablet()
    tablet.result_queue = queue.Queue()

    monkeypatch.setattr(tablet, "_decode_output", lambda value: value.decode("utf-8"))

    tablet.run_options = tablet_app.RunOptions(timeout_seconds=1.5)

    monkeypatch.setattr(
        tablet_app.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b" done ", stderr=b""),
    )
    tablet._run_cli_worker()
    assert tablet.result_queue.get_nowait() == ("success", "done")

    monkeypatch.setattr(
        tablet_app.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=3, stdout=b" output ", stderr=b" err "),
    )
    tablet._run_cli_worker()
    assert tablet.result_queue.get_nowait() == ("error", "err")

    monkeypatch.setattr(
        tablet_app.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=2, stdout=b" ", stderr=b" "),
    )
    tablet._run_cli_worker()
    assert tablet.result_queue.get_nowait() == ("error", "Unknown CLI failure.")

    def _raise_oserror(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr(tablet_app.subprocess, "run", _raise_oserror)
    tablet._run_cli_worker()
    status, message = tablet.result_queue.get_nowait()
    assert status == "error"
    assert "Could not run Telegraphy CLI" in message

    def _raise_timeout(*_args, **_kwargs):
        raise tablet_app.subprocess.TimeoutExpired(cmd=["x"], timeout=1.5)

    monkeypatch.setattr(tablet_app.subprocess, "run", _raise_timeout)
    tablet._run_cli_worker()
    assert tablet.result_queue.get_nowait() == ("error", "CLI worker timed out after 1.5s.")


def test_poll_queue_and_copy_and_output_and_draw(monkeypatch):
    tablet = _make_tablet()
    tablet.result_queue = queue.Queue()
    tablet.generate_button = MagicMock()
    tablet.copy_button = MagicMock()
    tablet.status = MagicMock()
    tablet.output = MagicMock()
    tablet.canvas = MagicMock()
    tablet.canvas.create_polygon.return_value = 999
    tablet.screen_window = 7
    tablet.latest_output = ""

    after_calls: list[tuple[int, object]] = []
    monkeypatch.setattr(tablet, "after", lambda delay, fn: after_calls.append((delay, fn)))

    output_messages: list[str] = []
    monkeypatch.setattr(tablet, "_set_output", lambda msg: output_messages.append(msg))

    tablet._poll_worker_queue()
    assert after_calls[-1] == (100, tablet._poll_worker_queue)

    tablet.result_queue.put(("success", "hello world"))
    tablet._poll_worker_queue()
    assert tablet.latest_output == "hello world"
    assert output_messages[-1] == "hello world"
    tablet.status.configure.assert_called_with(text="Generated. Ready to copy.")
    assert tablet.copy_button.configure.call_args_list[-1] == call(state="normal")

    tablet.result_queue.put(("error", "bad"))
    tablet._poll_worker_queue()
    assert tablet.latest_output == ""
    assert output_messages[-1] == "bad"
    tablet.status.configure.assert_called_with(text="Generation failed.")
    assert tablet.copy_button.configure.call_args_list[-1] == call(state="disabled")

    tablet.result_queue.put(("success", ""))
    tablet._poll_worker_queue()
    assert tablet.latest_output == ""
    assert output_messages[-1] == ""
    tablet.status.configure.assert_called_with(text="No output generated.")
    assert tablet.copy_button.configure.call_args_list[-1] == call(state="disabled")

    tablet.copy_latest_output()
    tablet.status.configure.assert_called_with(text="Nothing to copy yet.")

    monkeypatch.setattr(tablet, "clipboard_clear", MagicMock())
    monkeypatch.setattr(tablet, "clipboard_append", MagicMock())
    monkeypatch.setattr(tablet, "update_idletasks", MagicMock())

    tablet.latest_output = "copy me"
    tablet.copy_latest_output()
    tablet.clipboard_clear.assert_called_once_with()
    tablet.clipboard_append.assert_called_once_with("copy me")
    tablet.update_idletasks.assert_called_once_with()
    tablet.status.configure.assert_called_with(text="Copied to clipboard.")


def test_display_font_selection_and_dpi_fallback(monkeypatch):
    tablet = _make_tablet()
    tablet.output = MagicMock()
    tablet.canvas = MagicMock()
    tablet.screen_window = 7

    monkeypatch.setattr(tablet_app.tkfont, "families", lambda _parent: ["SF Pro Text"])
    monkeypatch.setattr(tablet_app.sys, "platform", "darwin")
    assert tablet._select_display_font() == "SF Pro Text"

    monkeypatch.setattr(tablet_app.sys, "platform", "plan9")
    assert tablet._select_display_font() == tablet_app.DEFAULT_FONT_FAMILY

    assert (
        tablet._pick_first_available_font(tuple(), set())
        == tablet_app.DEFAULT_FONT_FAMILY
    )

    tablet._dpi_cache = None

    def _raise_tcl_error(_value):
        raise tablet_app.tk.TclError("boom")

    monkeypatch.setattr(tablet, "winfo_fpixels", _raise_tcl_error)
    assert tablet._pixels_per_inch() == tablet_app.DEFAULT_DPI
    assert tablet._pixels_per_inch() == tablet_app.DEFAULT_DPI

    tablet_app.TelegraphyTablet._set_output(tablet, "render")
    assert tablet.output.configure.call_args_list[:1] == [call(state="normal")]
    tablet.output.delete.assert_called_once_with("1.0", "end")
    tablet.output.insert.assert_called_once_with("1.0", "render")
    assert tablet.output.configure.call_args_list[-1] == call(state="disabled")
    tablet.output.see.assert_called_once_with("1.0")

    evt = SimpleNamespace(width=500, height=300)
    rr_calls: list[tuple[float, ...]] = []
    monkeypatch.setattr(tablet, "_rounded_rectangle", lambda *args, **kwargs: rr_calls.append(args))
    tablet._redraw_tablet(evt)
    assert len(rr_calls) == 2
    tablet.canvas.delete.assert_called_once_with("tablet")
    tablet.canvas.coords.assert_called_once_with(7, 40, 40)
    tablet.canvas.itemconfigure.assert_called_once_with(7, width=420, height=220)

    polygon_id = tablet_app.TelegraphyTablet._rounded_rectangle(
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
    assert polygon_id is None
    tablet.canvas.create_polygon.assert_called_once()



def test_font_selection_by_platform(monkeypatch):
    tablet = _make_tablet()

    monkeypatch.setattr(tablet_app.tkfont, "families", lambda _root: ("Aptos Serif", "Segoe UI"))
    monkeypatch.setattr(tablet_app.sys, "platform", "win32")
    assert tablet._select_display_font() == "Aptos Serif"

    monkeypatch.setattr(tablet_app.tkfont, "families", lambda _root: ("Ubuntu",))
    monkeypatch.setattr(tablet_app.sys, "platform", "linux")
    assert tablet._select_display_font() == "Ubuntu"

    monkeypatch.setattr(tablet_app.tkfont, "families", lambda _root: (".AppleSystemUIFont",))
    monkeypatch.setattr(tablet_app.sys, "platform", "darwin")
    assert tablet._select_display_font() == ".AppleSystemUIFont"

    monkeypatch.setattr(tablet_app.tkfont, "families", lambda _root: ("Monospace",))
    monkeypatch.setattr(tablet_app.sys, "platform", "freebsd13")
    assert tablet._select_display_font() == tablet_app.DEFAULT_FONT_FAMILY


def test_font_fallback_helpers():
    assert tablet_app.TelegraphyTablet._pick_first_available_font(
        ("One", "Two", "Three"),
        {"zero", "three"},
    ) == "Three"

    assert tablet_app.TelegraphyTablet._pick_first_available_font(
        ("One", "Two", "Three"),
        {"zero"},
    ) == "One"

    assert (
        tablet_app.TelegraphyTablet._pick_first_available_font((), set())
        == tablet_app.DEFAULT_FONT_FAMILY
    )

def test_main_invokes_mainloop(monkeypatch):
    called: list[str] = []

    class FakeTablet:
        def __init__(self, run_options):
            called.append(str(run_options.seed))

        def mainloop(self):
            called.append("loop")

    monkeypatch.setattr(tablet_app, "TelegraphyTablet", FakeTablet)
    assert tablet_app.main(["--seed", "7"]) == 0
    assert called == ["7", "loop"]


def test_main_headless_tcl_error(monkeypatch, capsys):
    class FakeTablet:
        def __init__(self, run_options):
            raise tablet_app.tk.TclError("no display")

    monkeypatch.setattr(tablet_app, "TelegraphyTablet", FakeTablet)
    assert tablet_app.main([]) == 1
    assert "headless mode detected" in capsys.readouterr().err.lower()
