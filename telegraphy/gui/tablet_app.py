"""Tiny tkinter GUI for Telegraphy's story-brief CLI."""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Final

APP_TITLE: Final = "Telegraphy Tablet"
TABLET_BUTTON_STYLE: Final = "Tablet.TButton"
FONT_FAMILY: Final = "Segoe UI"
CLI_COMMAND: Final = [sys.executable, "-m", "telegraphy.story_brief", "--print-only"]


class TelegraphyTablet(tk.Tk):
    """A deliberately small tablet-shaped GUI wrapper around the CLI."""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("860x620")
        self.minsize(720, 520)
        self.configure(bg="#202124")

        self.latest_output = ""
        self.result_queue: queue.Queue[tuple[str, str]] = queue.Queue()

        self._configure_styles()
        self._build_shell()
        self._poll_worker_queue()

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            TABLET_BUTTON_STYLE,
            font=(FONT_FAMILY, 14, "bold"),
            padding=(18, 12),
        )
        style.configure(
            "Status.TLabel",
            background="#111827",
            foreground="#d1d5db",
            font=(FONT_FAMILY, 10),
        )

    def _build_shell(self) -> None:
        self.canvas = tk.Canvas(self, bg="#202124", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=22, pady=22)
        self.canvas.bind("<Configure>", self._redraw_tablet)

        self.screen = tk.Frame(self.canvas, bg="#111827")
        self.screen_window = self.canvas.create_window(0, 0, window=self.screen, anchor="nw")

        title = tk.Label(
            self.screen,
            text="TELEGRAPHY",
            bg="#111827",
            fg="#f9fafb",
            font=(FONT_FAMILY, 22, "bold"),
            pady=10,
        )
        title.pack(fill="x", padx=24, pady=(22, 0))

        subtitle = tk.Label(
            self.screen,
            text="Information Age Tablet • Story Brief Generator",
            bg="#111827",
            fg="#9ca3af",
            font=(FONT_FAMILY, 10),
        )
        subtitle.pack(fill="x", padx=24, pady=(0, 14))

        toolbar = tk.Frame(self.screen, bg="#111827")
        toolbar.pack(fill="x", padx=24, pady=(0, 14))

        self.generate_button = ttk.Button(
            toolbar,
            text="GENERATE!",
            style=TABLET_BUTTON_STYLE,
            command=self.generate_story_brief,
        )
        self.generate_button.pack(side="left")

        self.copy_button = ttk.Button(
            toolbar,
            text="COPY!",
            style=TABLET_BUTTON_STYLE,
            command=self.copy_latest_output,
        )
        self.copy_button.pack(side="left", padx=(12, 0))

        self.status = ttk.Label(toolbar, text="Ready.", style="Status.TLabel")
        self.status.pack(side="left", padx=(18, 0))

        output_frame = tk.Frame(self.screen, bg="#030712", bd=0)
        output_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        self.output = tk.Text(
            output_frame,
            wrap="word",
            bg="#030712",
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
            fill="#050505",
            outline="#3f3f46",
            width=3,
            tags="tablet",
        )
        self._rounded_rectangle(
            margin + bezel,
            margin + bezel,
            width - margin - bezel,
            height - margin - bezel,
            radius=22,
            fill="#111827",
            outline="#1f2937",
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
    ) -> int:
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
        return self.canvas.create_polygon(
            points,
            smooth=True,
            splinesteps=20,
            fill=fill,
            outline=outline,
            width=width,
            tags=tags,
        )

    def generate_story_brief(self) -> None:
        self.generate_button.configure(state="disabled")
        self.copy_button.configure(state="disabled")
        self.status.configure(text="Generating...")
        self._set_output("The typewriter goblin is warming up...")

        worker = threading.Thread(target=self._run_cli_worker, daemon=True)
        worker.start()

    def _run_cli_worker(self) -> None:
        try:
            completed = subprocess.run(
                CLI_COMMAND,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except OSError as exc:
            self.result_queue.put(("error", f"Could not run Telegraphy CLI:\n{exc}"))
            return

        if completed.returncode == 0:
            self.result_queue.put(("success", completed.stdout.strip()))
            return

        message = completed.stderr.strip() or completed.stdout.strip() or "Unknown CLI failure."
        self.result_queue.put(("error", message))

    def _poll_worker_queue(self) -> None:
        try:
            status, message = self.result_queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_worker_queue)
            return

        self.generate_button.configure(state="normal")
        self.copy_button.configure(state="normal")

        if status == "success":
            self.latest_output = message
            self._set_output(message)
            self.status.configure(text="Generated. Ready to copy.")
        else:
            self.latest_output = ""
            self._set_output(message)
            self.status.configure(text="Generation failed.")

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


def main() -> None:
    app = TelegraphyTablet()
    app.mainloop()


if __name__ == "__main__":
    main()
