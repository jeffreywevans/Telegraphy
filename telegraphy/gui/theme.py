"""Nord colors and shared ttk styles for Telegraphy's reading workspace."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Final

BACKGROUND: Final = "#2E3440"
SURFACE: Final = "#3B4252"
BORDER: Final = "#4C566A"
TEXT: Final = "#ECEFF4"
MUTED: Final = "#D8DEE9"
FROST: Final = "#88C0D0"
ACTIVE: Final = "#8FBCBB"
ERROR: Final = "#BF616A"
PRIMARY_BUTTON: Final = "Primary.TButton"


def configure_styles(root: tk.Misc, font_family: str) -> None:
    """Apply a consistent palette, including focus, active, and disabled states."""
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        "TButton",
        font=(font_family, 11),
        padding=(16, 10),
        background=SURFACE,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        focuscolor=FROST,
    )
    style.map(
        "TButton",
        background=[("active", BORDER)],
        foreground=[("disabled", MUTED)],
        bordercolor=[("focus", FROST)],
    )
    style.configure(PRIMARY_BUTTON, background=FROST, foreground=BACKGROUND)
    style.map(
        PRIMARY_BUTTON,
        background=[("disabled", BORDER), ("active", ACTIVE)],
        foreground=[("disabled", MUTED)],
    )
    style.configure(
        "TEntry",
        fieldbackground=BACKGROUND,
        foreground=TEXT,
        insertcolor=TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=8,
    )
    style.map("TEntry", bordercolor=[("focus", FROST)])
    style.configure(
        "Vertical.TScrollbar",
        background=BORDER,
        troughcolor=BACKGROUND,
        bordercolor=BACKGROUND,
        arrowcolor=MUTED,
    )
