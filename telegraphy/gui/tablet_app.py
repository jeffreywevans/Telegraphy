"""A Nord reading workspace for Telegraphy’s story-brief CLI."""

from __future__ import annotations

import argparse
import math
import queue
import sys
import threading
import tkinter as tk
from importlib.metadata import PackageNotFoundError, version
from tkinter import font as tkfont
from tkinter import ttk
from typing import Final

from telegraphy.gui import theme
from telegraphy.gui.cli_runner import run_story_brief_cli
from telegraphy.gui.models import (
    DEFAULT_CLI_TIMEOUT_SECONDS,
    RunOptions,
    RunOptionsValidationError,
    resolve_run_options,
)
from telegraphy.gui.preview import brief_preview


def _read_app_version() -> str:
    """Read the running distribution's version without a duplicated release number."""
    try:
        return version("Commuted_Telegraphy")
    except PackageNotFoundError:
        return "development"


APP_VERSION: Final[str] = _read_app_version()
APP_TITLE: Final = f"Telegraphy · v{APP_VERSION}"
DEFAULT_FONT_FAMILY: Final = "Segoe UI"
DEFAULT_DPI: Final = 96
WINDOW_WIDTH: Final = 1120
WINDOW_HEIGHT: Final = 800
MIN_WINDOW_WIDTH: Final = 760
MIN_WINDOW_HEIGHT: Final = 520
EMPTY_MESSAGE: Final = "Your next story starts here.\n\nGenerate a brief, then make it yours."


def _parse_timeout_seconds(raw_timeout: str) -> float:
    """Parse a positive, finite CLI timeout for argparse."""
    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--timeout must be a finite number greater than zero"
        ) from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("--timeout must be a finite number greater than zero")
    return timeout


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch the Telegraphy desktop GUI.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Seed forwarded to the CLI for deterministic generation.",
    )
    parser.add_argument("--date", help="Date forwarded to the CLI (YYYY-MM-DD).")
    parser.add_argument(
        "--timeout",
        type=_parse_timeout_seconds,
        default=DEFAULT_CLI_TIMEOUT_SECONDS,
        help="Seconds to wait for CLI completion before showing a timeout error.",
    )
    return parser


class TelegraphyTablet(tk.Tk):
    """A spacious desktop reading workspace; the class name preserves launcher compatibility."""

    def __init__(self, run_options: RunOptions | None = None) -> None:
        super().__init__()
        self._dpi_cache: int | None = None
        self.title(APP_TITLE)
        width = self._default_window_width()
        self.geometry(f"{width}x{self._default_window_height()}")
        self.minsize(self._minimum_window_width(), self._minimum_window_height())
        self.configure(bg=theme.BACKGROUND)

        self.latest_output = ""
        self.run_options = run_options or RunOptions()
        self.result_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._worker_active = False

        self.font_family = self._select_display_font()

        self._configure_styles()
        self._build_shell()

    def _pixels_per_inch(self) -> int:
        if self._dpi_cache is not None:
            return self._dpi_cache
        try:
            self._dpi_cache = max(int(round(float(self.winfo_fpixels("1i")))), 1)
        except tk.TclError, ValueError, AttributeError, RecursionError:
            self._dpi_cache = DEFAULT_DPI
        return self._dpi_cache

    def _scaled_pixels(self, base_pixels: int) -> int:
        return max(int(round(base_pixels * (self._pixels_per_inch() / DEFAULT_DPI))), 1)

    def _default_window_width(self) -> int:
        return self._scaled_pixels(WINDOW_WIDTH)

    def _minimum_window_width(self) -> int:
        return self._scaled_pixels(MIN_WINDOW_WIDTH)

    def _default_window_height(self) -> int:
        return self._scaled_pixels(WINDOW_HEIGHT)

    def _minimum_window_height(self) -> int:
        return self._scaled_pixels(MIN_WINDOW_HEIGHT)

    def _select_display_font(self) -> str:
        available_fonts = {name.lower() for name in tkfont.families(self)}

        if sys.platform.startswith("win"):
            return self._pick_first_available_font(
                ("Segoe UI", "Aptos", "Arial"),
                available_fonts,
            )

        if sys.platform == "linux":
            return self._pick_first_available_font(
                ("Noto Sans", "Ubuntu", "DejaVu Sans", "Helvetica"),
                available_fonts,
            )

        if sys.platform == "darwin":
            # Apple platforms should prefer the system UI font (San Francisco).
            return self._pick_first_available_font(
                (".AppleSystemUIFont", "SF Pro Text", "Helvetica Neue"),
                available_fonts,
            )

        return DEFAULT_FONT_FAMILY

    @staticmethod
    def _pick_first_available_font(candidates: tuple[str, ...], available_fonts: set[str]) -> str:
        for font_name in candidates:
            if font_name.lower() in available_fonts:
                return font_name
        return candidates[0] if candidates else DEFAULT_FONT_FAMILY

    def _configure_styles(self) -> None:
        theme.configure_styles(self, self.font_family)

    def _build_shell(self) -> None:
        self.screen = tk.Frame(self, bg=theme.BACKGROUND)
        self.screen.pack(fill="both", expand=True, padx=24, pady=16)
        self._build_header()
        self._build_controls()
        self.error_label = tk.Label(
            self.screen,
            text="",
            bg=theme.BACKGROUND,
            fg=theme.ERROR,
            font=(self.font_family, 10),
            anchor="w",
            justify="left",
            wraplength=680,
        )
        self.error_label.pack(fill="x", pady=(0, 8))
        self.screen.bind("<Configure>", self._resize_message)
        self._build_document()
        self.bind("<Control-Return>", lambda _event: self.generate_story_brief())
        self.bind("<Command-Return>", lambda _event: self.generate_story_brief())

    def _build_header(self) -> None:
        header = tk.Frame(self.screen, bg=theme.BACKGROUND)
        header.pack(fill="x", pady=(0, 18))
        tk.Label(
            header,
            text="Telegraphy",
            bg=theme.BACKGROUND,
            fg=theme.TEXT,
            font=(self.font_family, 22, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text=f"v{APP_VERSION}",
            bg=theme.BACKGROUND,
            fg=theme.MUTED,
            font=(self.font_family, 10),
        ).pack(side="left", padx=12)
        self.status = tk.Label(
            header,
            text="Ready",
            bg=theme.BACKGROUND,
            fg=theme.FROST,
            font=(self.font_family, 10),
        )
        self.status.pack(side="right")

    def _build_controls(self) -> None:
        toolbar = tk.Frame(self.screen, bg=theme.SURFACE, padx=14, pady=12)
        toolbar.pack(fill="x")
        toolbar.columnconfigure(4, weight=1)
        self.seed_var = tk.StringVar(
            value=str(self.run_options.seed) if self.run_options.seed is not None else "",
        )
        self.date_var = tk.StringVar(value=self.run_options.date or "")
        for column, label, variable, width in (
            (0, "Seed (optional)", self.seed_var, 10),
            (2, "Date (YYYY-MM-DD)", self.date_var, 14),
        ):
            tk.Label(
                toolbar,
                text=label,
                bg=theme.SURFACE,
                fg=theme.MUTED,
                font=(self.font_family, 9),
                anchor="w",
            ).grid(row=0, column=column, sticky="w", padx=(0, 14), pady=(0, 5))
            ttk.Entry(
                toolbar,
                width=width,
                textvariable=variable,
                font=(self.font_family, 11),
            ).grid(row=1, column=column, sticky="ew", padx=(0, 14))
        self.generate_button = ttk.Button(
            toolbar,
            text="Generate brief",
            style=theme.PRIMARY_BUTTON,
            command=self.generate_story_brief,
        )
        self.generate_button.grid(row=1, column=5, padx=(12, 8))
        self.copy_button = ttk.Button(
            toolbar,
            text="Copy",
            command=self.copy_latest_output,
            state="disabled",
        )
        self.copy_button.grid(row=1, column=6)

    def _build_document(self) -> None:
        document = tk.Frame(
            self.screen,
            bg=theme.BACKGROUND,
            highlightthickness=1,
            highlightbackground=theme.BORDER,
        )
        document.pack(fill="both", expand=True)
        self.output = tk.Text(
            document,
            width=72,
            wrap="word",
            bg=theme.BACKGROUND,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            selectbackground=theme.BORDER,
            selectforeground=theme.TEXT,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=theme.BACKGROUND,
            highlightcolor=theme.FROST,
            padx=28,
            pady=24,
            font=(self.font_family, 12),
            spacing1=3,
            spacing3=5,
            undo=False,
        )
        self.output.pack(side="left", fill="both", expand=True)
        self.output.bind("<Tab>", self._focus_next_control)
        self.output.bind("<Shift-Tab>", self._focus_previous_control)
        self.output.bind("<ISO_Left_Tab>", self._focus_previous_control)
        scrollbar = ttk.Scrollbar(document, command=self.output.yview)
        scrollbar.pack(side="right", fill="y")
        self.output.configure(yscrollcommand=scrollbar.set)
        self.output.tag_configure(
            "heading", foreground=theme.FROST, font=(self.font_family, 18, "bold"), spacing1=18
        )
        self.output.tag_configure(
            "title", foreground=theme.TEXT, font=(self.font_family, 25, "bold"), spacing3=12
        )
        self.output.tag_configure(
            "metadata", foreground=theme.MUTED, font="TkFixedFont", spacing1=0, spacing3=0
        )
        self.output.tag_configure(
            "empty", foreground=theme.MUTED, justify="center", spacing1=30, spacing3=12
        )
        self._set_output(EMPTY_MESSAGE)
        self.output.tag_add("empty", "1.0", "end")

    def _focus_next_control(self, _event: tk.Event) -> str:
        next_control = self.output.tk_focusNext()
        if next_control is not None:
            next_control.focus_set()
        return "break"

    def _focus_previous_control(self, _event: tk.Event) -> str:
        previous_control = self.output.tk_focusPrev()
        if previous_control is not None:
            previous_control.focus_set()
        return "break"

    def _resize_message(self, event: tk.Event) -> None:
        self.error_label.configure(wraplength=max(event.width - 16, 1))

    def _resolve_run_options(self) -> RunOptions | None:
        result = resolve_run_options(
            seed_text=self.seed_var.get(),
            date_text=self.date_var.get(),
            current_options=self.run_options,
        )
        if isinstance(result, RunOptionsValidationError):
            self.result_queue.put(("error", result.message))
            return None
        return result

    def generate_story_brief(self) -> None:
        if self._worker_active:
            return
        resolved_options = self._resolve_run_options()
        self._worker_active = True
        if resolved_options is not None:
            self.run_options = resolved_options
            self.generate_button.configure(state="disabled")
            self.error_label.configure(text="")
            self.status.configure(text="Generating…")
            worker = threading.Thread(target=self._run_cli_worker, daemon=True)
            worker.start()
        self._poll_worker_queue()

    def _run_cli_worker(self) -> None:
        try:
            result = run_story_brief_cli(self.run_options)
        except Exception as exc:
            # This is the thread boundary: always wake the UI even if an unexpected
            # dependency or subprocess failure escapes the normal runner handling.
            self.result_queue.put(("error", f"Unexpected CLI worker failure: {exc}"))
            return
        self.result_queue.put((result.status, result.message))

    def _poll_worker_queue(self) -> None:
        if not self._worker_active:
            return

        try:
            status, message = self.result_queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_worker_queue)
            return

        self._worker_active = False

        self.generate_button.configure(state="normal")

        if status == "success" and message:
            self.copy_button.configure(state="normal")
            self.error_label.configure(text="")
            self.latest_output = message
            self._set_output(brief_preview(message))
            self.status.configure(text="Generated. Ready to copy.")
        else:
            self.error_label.configure(
                text=message or "The generator returned no output. Try again."
            )
            status_text = "Generation failed." if status != "success" else "No output generated."
            self.status.configure(text=status_text)

    def copy_latest_output(self) -> None:
        if not self.latest_output:
            self.status.configure(text="Nothing to copy yet.")
            return

        self.clipboard_clear()
        self.clipboard_append(self.latest_output)
        self.update_idletasks()
        self.status.configure(text="Copied to clipboard.")

    def _set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        display_lines = [line.removeprefix("## ").removeprefix("# ") for line in text.splitlines()]
        self.output.insert("1.0", "\n".join(display_lines))
        in_metadata = False
        for number, line in enumerate(text.splitlines(), start=1):
            if line == "---":
                in_metadata = not in_metadata
            if in_metadata or line == "---":
                self.output.tag_add("metadata", f"{number}.0", f"{number}.end")
            elif line.startswith("# "):
                self.output.tag_add("title", f"{number}.0", f"{number}.end")
            elif line.startswith("## "):
                self.output.tag_add("heading", f"{number}.0", f"{number}.end")
        self.output.configure(state="disabled")
        self.output.see("1.0")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        app = TelegraphyTablet(
            RunOptions(seed=args.seed, date=args.date, timeout_seconds=args.timeout),
        )
    except tk.TclError as exc:
        print(
            "Unable to start Telegraphy GUI. "
            "A display environment is required (headless mode detected).",
            file=sys.stderr,
        )
        print(f"Details: {exc}", file=sys.stderr)
        return 1

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
