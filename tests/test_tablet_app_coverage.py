from __future__ import annotations

import queue
from types import SimpleNamespace

from telegraphy.gui import tablet_app


class DummyWidget:
    def __init__(self) -> None:
        self.configs: list[dict[str, object]] = []

    def configure(self, **kwargs: object) -> None:
        self.configs.append(kwargs)


class DummyOutput(DummyWidget):
    def __init__(self) -> None:
        super().__init__()
        self.deleted: list[tuple[str, str]] = []
        self.inserted: list[tuple[str, str]] = []
        self.seen: list[str] = []

    def delete(self, start: str, end: str) -> None:
        self.deleted.append((start, end))

    def insert(self, start: str, text: str) -> None:
        self.inserted.append((start, text))

    def see(self, index: str) -> None:
        self.seen.append(index)


class DummyCanvas:
    def __init__(self) -> None:
        self.deleted_tags: list[str] = []
        self.ovals: list[tuple[float, ...]] = []
        self.coords_calls: list[tuple[int, float, float]] = []
        self.itemconfigure_calls: list[tuple[int, dict[str, object]]] = []
        self.lowered: list[str] = []
        self.polygon_call: dict[str, object] | None = None

    def delete(self, tag: str) -> None:
        self.deleted_tags.append(tag)

    def create_oval(self, *args: float, **kwargs: object) -> None:
        self.ovals.append((*args,))

    def coords(self, window: int, x: float, y: float) -> None:
        self.coords_calls.append((window, x, y))

    def itemconfigure(self, window: int, **kwargs: object) -> None:
        self.itemconfigure_calls.append((window, kwargs))

    def tag_lower(self, tag: str) -> None:
        self.lowered.append(tag)

    def create_polygon(self, points: list[float], **kwargs: object) -> int:
        self.polygon_call = {"points": points, **kwargs}
        return 999


def _make_tablet() -> tablet_app.TelegraphyTablet:
    return tablet_app.TelegraphyTablet.__new__(tablet_app.TelegraphyTablet)


def test_init_and_configure_style_and_build(monkeypatch):
    tablet = _make_tablet()

    monkeypatch.setattr(tablet_app.tk.Tk, "__init__", lambda self: None)
    monkeypatch.setattr(tablet, "title", lambda _title: None)
    monkeypatch.setattr(tablet, "geometry", lambda _geometry: None)
    monkeypatch.setattr(tablet, "minsize", lambda _w, _h: None)
    monkeypatch.setattr(tablet, "configure", lambda **_kwargs: None)

    calls: list[str] = []
    monkeypatch.setattr(tablet, "_configure_styles", lambda: calls.append("styles"))
    monkeypatch.setattr(tablet, "_build_shell", lambda: calls.append("shell"))
    monkeypatch.setattr(tablet, "_poll_worker_queue", lambda: calls.append("poll"))

    tablet.__init__()

    assert tablet.latest_output == ""
    assert isinstance(tablet.result_queue, queue.Queue)
    assert calls == ["styles", "shell", "poll"]


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
    tablet.generate_button = DummyWidget()
    tablet.copy_button = DummyWidget()
    tablet.status = DummyWidget()

    set_output_calls: list[str] = []
    monkeypatch.setattr(tablet, "_set_output", lambda msg: set_output_calls.append(msg))

    thread_record: dict[str, object] = {}

    class FakeThread:
        def __init__(self, *, target, daemon):
            thread_record["target"] = target
            thread_record["daemon"] = daemon

        def start(self):
            thread_record["started"] = True

    monkeypatch.setattr(tablet_app.threading, "Thread", FakeThread)

    tablet.generate_story_brief()

    assert tablet.generate_button.configs[-1] == {"state": "disabled"}
    assert tablet.copy_button.configs[-1] == {"state": "disabled"}
    assert tablet.status.configs[-1] == {"text": "Generating..."}
    assert set_output_calls == ["The typewriter goblin is warming up..."]
    assert thread_record == {"target": tablet._run_cli_worker, "daemon": True, "started": True}


def test_run_cli_worker_success_error_and_exception(monkeypatch):
    tablet = _make_tablet()
    tablet.result_queue = queue.Queue()

    monkeypatch.setattr(tablet, "_decode_output", lambda value: value.decode("utf-8"))

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


def test_poll_queue_and_copy_and_output_and_draw(monkeypatch):
    tablet = _make_tablet()
    tablet.result_queue = queue.Queue()
    tablet.generate_button = DummyWidget()
    tablet.copy_button = DummyWidget()
    tablet.status = DummyWidget()
    tablet.output = DummyOutput()
    tablet.canvas = DummyCanvas()
    tablet.screen_window = 7
    tablet.latest_output = ""

    after_calls: list[tuple[int, object]] = []
    monkeypatch.setattr(tablet, "after", lambda delay, fn: after_calls.append((delay, fn)))

    output_messages: list[str] = []
    monkeypatch.setattr(tablet, "_set_output", lambda msg: output_messages.append(msg))

    tablet._poll_worker_queue()
    assert after_calls and after_calls[-1][0] == 100

    tablet.result_queue.put(("success", "hello world"))
    tablet._poll_worker_queue()
    assert tablet.latest_output == "hello world"
    assert output_messages[-1] == "hello world"
    assert tablet.status.configs[-1] == {"text": "Generated. Ready to copy."}

    tablet.result_queue.put(("error", "bad"))
    tablet._poll_worker_queue()
    assert tablet.latest_output == ""
    assert output_messages[-1] == "bad"
    assert tablet.status.configs[-1] == {"text": "Generation failed."}

    tablet.copy_latest_output()
    assert tablet.status.configs[-1] == {"text": "Nothing to copy yet."}

    calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(tablet, "clipboard_clear", lambda: calls.append(("clear", None)))
    monkeypatch.setattr(tablet, "clipboard_append", lambda text: calls.append(("append", text)))
    monkeypatch.setattr(tablet, "update_idletasks", lambda: calls.append(("update", None)))

    tablet.latest_output = "copy me"
    tablet.copy_latest_output()
    assert calls == [("clear", None), ("append", "copy me"), ("update", None)]
    assert tablet.status.configs[-1] == {"text": "Copied to clipboard."}

    tablet_app.TelegraphyTablet._set_output(tablet, "render")
    assert tablet.output.deleted == [("1.0", "end")]
    assert tablet.output.inserted == [("1.0", "render")]
    assert tablet.output.seen == ["1.0"]

    evt = SimpleNamespace(width=500, height=300)
    rr_calls: list[tuple[float, ...]] = []
    monkeypatch.setattr(tablet, "_rounded_rectangle", lambda *args, **kwargs: rr_calls.append(args))
    tablet._redraw_tablet(evt)
    assert len(rr_calls) == 2
    assert tablet.canvas.deleted_tags == ["tablet"]

    polygon_id = tablet_app.TelegraphyTablet._rounded_rectangle(tablet, 0, 0, 10, 10, radius=1, fill="f", outline="o", width=2, tags="t")
    assert polygon_id == 999
    assert tablet.canvas.polygon_call is not None


def test_main_invokes_mainloop(monkeypatch):
    called: list[str] = []

    class FakeTablet:
        def mainloop(self):
            called.append("loop")

    monkeypatch.setattr(tablet_app, "TelegraphyTablet", FakeTablet)
    tablet_app.main()
    assert called == ["loop"]
