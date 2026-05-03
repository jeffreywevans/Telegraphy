"""Tiny tkinter GUI for Telegraphy's story-brief CLI."""

from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from locale import getpreferredencoding
from tkinter import font as tkfont
from tkinter import ttk
from typing import Final

APP_TITLE: Final = "Telegraphy Tablet"
TABLET_BUTTON_STYLE: Final = "Tablet.TButton"
DEFAULT_FONT_FAMILY: Final = "Segoe UI"
DEFAULT_CLI_TIMEOUT_SECONDS: Final = 30
TABLET_EXTRA_WIDTH_INCHES_PER_SIDE: Final = 2
TABLET_BASE_WIDTH_PIXELS: Final = 860
TABLET_BASE_HEIGHT_PIXELS: Final = 620
TABLET_BASE_MIN_WIDTH_PIXELS: Final = 720
TABLET_BASE_MIN_HEIGHT_PIXELS: Final = 520
CLI_TEXT_WIDTH_CHARACTERS: Final = 100

TABLET_OUTER_SECTION_COLOR: Final = "#D91E1E"
TABLET_MIDDLE_SECTION_COLOR: Final = "#F2F2F2"
TABLET_INNER_SECTION_COLOR: Final = "#0D0D0D"
TABLET_OUTER_OUTLINE_COLOR: Final = "#A6A6A6"
TABLET_MIDDLE_OUTLINE_COLOR: Final = "#1f2937"


@dataclass(frozen=True)
class RunOptions:
    seed: int | None = None
    date: str | None = None
    timeout_seconds: float = DEFAULT_CLI_TIMEOUT_SECONDS


def _build_cli_command(options: RunOptions) -> list[str]:
    command = [sys.executable, "-m", "telegraphy.story_brief", "--print-only"]
    if options.seed is not None:
        command.extend(["--seed", str(options.seed)])
    if options.date:
        command.extend(["--date", options.date])
    return command


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
        type=float,
        default=DEFAULT_CLI_TIMEOUT_SECONDS,
        help="Seconds to wait for CLI completion before showing a timeout error.",
    )
    return parser


class TelegraphyTablet(tk.Tk):
    """A deliberately small tablet-shaped GUI wrapper around the CLI."""

    def __init__(self, run_options: RunOptions | None = None) -> None:
        super().__init__()
        self.title(APP_TITLE)
        width = self._default_window_width()
        self.geometry(f"{width}x{TABLET_BASE_HEIGHT_PIXELS}")
        self.minsize(self._minimum_window_width(), TABLET_BASE_MIN_HEIGHT_PIXELS)
        self.configure(bg="#202124")

        self.latest_output = ""
        self.run_options = run_options or RunOptions()
        self.result_queue: queue.Queue[tuple[str, str]] = queue.Queue()

        self.font_family = self._select_display_font()

        self._configure_styles()
        self._build_shell()
        self._poll_worker_queue()

    def _pixels_per_inch(self) -> int:
        try:
            return max(int(round(float(self.winfo_fpixels("1i")))), 1)
        except (tk.TclError, ValueError, AttributeError, RecursionError):
            return 96

    def _extra_window_width_pixels(self) -> int:
        return 2 * TABLET_EXTRA_WIDTH_INCHES_PER_SIDE * self._pixels_per_inch()

    def _default_window_width(self) -> int:
        return TABLET_BASE_WIDTH_PIXELS + self._extra_window_width_pixels()

    def _minimum_window_width(self) -> int:
        return TABLET_BASE_MIN_WIDTH_PIXELS + self._extra_window_width_pixels()

    def _select_display_font(self) -> str:
        available_fonts = {name.lower() for name in tkfont.families(self)}

        if sys.platform.startswith("win"):
            return self._pick_first_available_font(
                ("Aptos Serif", "Segoe UI", "Times New Roman"),
                available_fonts,
            )

        if sys.platform == "linux":
            return self._pick_first_available_font(
                ("Noto Serif", "Ubuntu", "DejaVu Sans"),
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
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            TABLET_BUTTON_STYLE,
            font=(self.font_family, 14, "bold"),
            padding=(18, 12),
        )
        style.configure(
            "Status.TLabel",
            background=TABLET_INNER_SECTION_COLOR,
            foreground="#d1d5db",
            font=(self.font_family, 10),
        )

    def _build_shell(self) -> None:
        self.canvas = tk.Canvas(self, bg="#202124", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=22, pady=22)
        self.canvas.bind("<Configure>", self._redraw_tablet)

        self.screen = tk.Frame(self.canvas, bg=TABLET_INNER_SECTION_COLOR)
        self.screen_window = self.canvas.create_window(0, 0, window=self.screen, anchor="nw")

        screen_bg = self.screen.cget("bg")

        title = tk.Label(
            self.screen,
            text="TELEGRAPHY",
            bg=screen_bg,
            fg="#f9fafb",
            font=(self.font_family, 22, "bold"),
            pady=10,
        )
        title.pack(fill="x", padx=24, pady=(22, 0))

        subtitle = tk.Label(
            self.screen,
            text="Information Age Tablet • Story Brief Generator",
            bg=screen_bg,
            fg="#9ca3af",
            font=(self.font_family, 10),
        )
        subtitle.pack(fill="x", padx=24, pady=(0, 14))

        toolbar = tk.Frame(self.screen, bg=screen_bg)
        toolbar.pack(fill="x", padx=24, pady=(0, 14))

        self.generate_button = ttk.Button(
            toolbar,
            text="GENERATE!",
            style=TABLET_BUTTON_STYLE,
            command=self.generate_story_brief,
        )
        self.generate_button.pack(side="left")

        controls = tk.Frame(toolbar, bg=toolbar.cget("bg"))
        controls.pack(side="left", padx=(12, 0))

        tk.Label(
            controls,
            text="Seed",
            bg=controls.cget("bg"),
            fg="#9ca3af",
            font=(self.font_family, 9),
        ).grid(row=0, column=0, sticky="w")
        self.seed_var = tk.StringVar(
            value=str(self.run_options.seed) if self.run_options.seed is not None else "",
        )
        seed_entry = ttk.Entry(controls, width=10, textvariable=self.seed_var)
        seed_entry.grid(row=1, column=0, padx=(0, 8))

        tk.Label(
            controls,
            text="Date",
            bg=controls.cget("bg"),
            fg="#9ca3af",
            font=(self.font_family, 9),
        ).grid(row=0, column=1, sticky="w")
        self.date_var = tk.StringVar(value=self.run_options.date or "")
        date_entry = ttk.Entry(controls, width=12, textvariable=self.date_var)
        date_entry.grid(row=1, column=1)

        self.copy_button = ttk.Button(
            toolbar,
            text="COPY!",
            style=TABLET_BUTTON_STYLE,
            command=self.copy_latest_output,
        )
        self.copy_button.pack(side="left", padx=(12, 0))

        self.status = ttk.Label(toolbar, text="Ready.", style="Status.TLabel")
        self.status.pack(side="left", padx=(18, 0))

        output_frame = tk.Frame(self.screen, bg=screen_bg, bd=0)
        output_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        self.output = tk.Text(
            output_frame,
            width=CLI_TEXT_WIDTH_CHARACTERS,
            wrap="word",
            bg=output_frame.cget("bg"),
            fg="#e5e7eb",
            insertbackground="#e5e7eb",
            relief="flat",
            padx=16,
            pady=16,
            font=("Consolas", 11),
            undo=False,
        )
        self.output.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(output_frame, command=self.output.yview)
        scrollbar.pack(side="right", fill="y")
        self.output.configure(yscrollcommand=scrollbar.set)

        self._set_output(
            "Press GENERATE! to run:\n"
            "python -m telegraphy.story_brief --print-only\n\n"
            "The generated brief will appear here. COPY! puts it on the clipboard."
        )

    def _redraw_tablet(self, event: tk.Event) -> None:
        width = int(event.width)
        height = int(event.height)
        margin = 10
        bezel = 28

        self.canvas.delete("tablet")
        self._rounded_rectangle(
            margin,
            margin,
            width - margin,
            height - margin,
            radius=42,
            fill=TABLET_OUTER_SECTION_COLOR,
            outline=TABLET_OUTER_OUTLINE_COLOR,
            width=3,
            tags="tablet",
        )
        self._rounded_rectangle(
            margin + bezel,
            margin + bezel,
            width - margin - bezel,
            height - margin - bezel,
            radius=22,
            fill=TABLET_MIDDLE_SECTION_COLOR,
            outline=TABLET_MIDDLE_OUTLINE_COLOR,
            width=2,
            tags="tablet",
        )

        self.canvas.create_oval(
            width / 2 - 4,
            margin + 11,
            width / 2 + 4,
            margin + 19,
            fill="#27272a",
            outline="",
            tags="tablet",
        )

        self.canvas.coords(self.screen_window, margin + bezel + 2, margin + bezel + 2)
        self.canvas.itemconfigure(
            self.screen_window,
            width=width - 2 * (margin + bezel + 2),
            height=height - 2 * (margin + bezel + 2),
        )
        self.canvas.tag_lower("tablet")

    def _rounded_rectangle(
        self,
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
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        self.canvas.create_polygon(
            points,
            smooth=True,
            splinesteps=20,
            fill=fill,
            outline=outline,
            width=width,
            tags=tags,
        )

    def _resolve_run_options(self) -> RunOptions | None:
        seed_text = self.seed_var.get().strip()
        date_text = self.date_var.get().strip()

        seed_value = self.run_options.seed
        if seed_text:
            try:
                seed_value = int(seed_text)
            except ValueError:
                self.result_queue.put(("error", f"Invalid seed: {seed_text!r}. Enter an integer."))
                return None

        date_value = date_text or self.run_options.date
        return RunOptions(
            seed=seed_value,
            date=date_value,
            timeout_seconds=self.run_options.timeout_seconds,
        )

    def generate_story_brief(self) -> None:
        self.generate_button.configure(state="disabled")
        self.copy_button.configure(state="disabled")
        resolved_options = self._resolve_run_options()
        if resolved_options is None:
            self.status.configure(text="Generation failed.")
            return
        self.run_options = resolved_options
        self.status.configure(text="Generating...")
        self._set_output("Kendall is warming her sweet ass up...")

        worker = threading.Thread(target=self._run_cli_worker, daemon=True)
        worker.start()

    def _run_cli_worker(self) -> None:
        try:
            completed = subprocess.run(
                _build_cli_command(self.run_options),
                check=False,
                capture_output=True,
                text=False,
                timeout=self.run_options.timeout_seconds,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired:
            self.result_queue.put(
                (
                    "error",
                    f"CLI worker timed out after {self.run_options.timeout_seconds:g}s.",
                )
            )
            return
        except OSError as exc:
            self.result_queue.put(("error", f"Could not run Telegraphy CLI:\n{exc}"))
            return

        stdout = self._decode_output(completed.stdout)
        stderr = self._decode_output(completed.stderr)

        if completed.returncode == 0:
            self.result_queue.put(("success", stdout.strip()))
            return

        message = stderr.strip() or stdout.strip() or "Unknown CLI failure."
        self.result_queue.put(("error", message))

    def _decode_output(self, output: bytes) -> str:
        preferred_encoding = getpreferredencoding(False) or "utf-8"

        try:
            return output.decode(preferred_encoding)
        except (UnicodeDecodeError, LookupError):
            return output.decode("utf-8", errors="replace")

    def _poll_worker_queue(self) -> None:
        try:
            status, message = self.result_queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_worker_queue)
            return

        self.generate_button.configure(state="normal")

        if status == "success" and message:
            self.copy_button.configure(state="normal")
            self.latest_output = message
            self._set_output(message)
            self.status.configure(text="Generated. Ready to copy.")
        else:
            self.copy_button.configure(state="disabled")
            self.latest_output = ""
            self._set_output(message)
            status_text = "Generation failed." if status != "success" else "No output generated."
            self.status.configure(text=status_text)

        self.after(100, self._poll_worker_queue)

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
        self.output.insert("1.0", text)
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
