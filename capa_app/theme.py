"""Color palette, fonts and ttk style setup for the CAPA desktop app."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# ------------------------------------------------------------- palette
BG = "#0f1420"          # window background (deep navy)
BG_SIDEBAR = "#151c2c"
BG_CARD = "#1a2233"
BG_INPUT = "#232d42"
BORDER = "#2c3850"
FG = "#e8edf6"
FG_MUTED = "#93a0b8"
ACCENT = "#3b82f6"      # primary blue
ACCENT_HOVER = "#2f6ad0"
GREEN = "#22c55e"
AMBER = "#f59e0b"
RED = "#ef4444"
PURPLE = "#a78bfa"
CYAN = "#22d3ee"

STATUS_COLORS = {
    "Open": CYAN,
    "In Progress": ACCENT,
    "Verification": AMBER,
    "Closed": GREEN,
    "Overdue": RED,
}

PRIORITY_COLORS = {
    "Low": FG_MUTED,
    "Medium": CYAN,
    "High": AMBER,
    "Critical": RED,
}

FONTS = {
    "h1": ("Segoe UI", 22, "bold"),
    "h2": ("Segoe UI", 15, "bold"),
    "h3": ("Segoe UI", 12, "bold"),
    "body": ("Segoe UI", 10),
    "body_bold": ("Segoe UI", 10, "bold"),
    "muted": ("Segoe UI", 9),
    "stat_num": ("Segoe UI", 26, "bold"),
    "nav": ("Segoe UI", 11),
    "nav_active": ("Segoe UI", 11, "bold"),
    "small": ("Segoe UI", 9),
}


def apply_styles(root: tk.Tk) -> None:
    root.configure(bg=BG)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=BG, foreground=FG, fieldbackground=BG_INPUT,
                    bordercolor=BORDER, lightcolor=BG, darkcolor=BG,
                    font=FONTS["body"], troughcolor=BG_CARD)

    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=BG_CARD)
    style.configure("Sidebar.TFrame", background=BG_SIDEBAR)
    style.configure("Input.TFrame", background=BG_INPUT)

    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Card.TLabel", background=BG_CARD, foreground=FG)
    style.configure("Muted.TLabel", background=BG, foreground=FG_MUTED)
    style.configure("CardMuted.TLabel", background=BG_CARD, foreground=FG_MUTED)
    style.configure("H1.TLabel", background=BG, foreground=FG, font=FONTS["h1"])
    style.configure("H2.TLabel", background=BG, foreground=FG, font=FONTS["h2"])
    style.configure("CardH2.TLabel", background=BG_CARD, foreground=FG, font=FONTS["h2"])
    style.configure("H3.TLabel", background=BG, foreground=FG, font=FONTS["h3"])
    style.configure("CardH3.TLabel", background=BG_CARD, foreground=FG, font=FONTS["h3"])
    style.configure("StatNum.TLabel", background=BG_CARD, foreground=FG,
                    font=FONTS["stat_num"])

    style.configure("TButton", background=BG_INPUT, foreground=FG,
                    borderwidth=0, focuscolor=BG_INPUT, padding=(12, 7),
                    font=FONTS["body_bold"])
    style.map("TButton",
              background=[("active", BORDER)], foreground=[("disabled", FG_MUTED)])

    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff")
    style.map("Accent.TButton", background=[("active", ACCENT_HOVER)])

    style.configure("Danger.TButton", background="#5b1f24", foreground="#ffd7d9")
    style.map("Danger.TButton", background=[("active", "#7a2a30")])

    style.configure("Ghost.TButton", background=BG, foreground=FG_MUTED)
    style.map("Ghost.TButton", background=[("active", BG_CARD)],
              foreground=[("active", FG)])

    style.configure("TEntry", fieldbackground=BG_INPUT, foreground=FG,
                    insertcolor=FG, borderwidth=1, relief="flat", padding=7)
    style.configure("TCombobox", fieldbackground=BG_INPUT, background=BG_INPUT,
                    foreground=FG, arrowcolor=FG, borderwidth=1, padding=5)
    style.map("TCombobox",
              fieldbackground=[("readonly", BG_INPUT)],
              foreground=[("readonly", FG)],
              selectbackground=[("readonly", BG_INPUT)],
              selectforeground=[("readonly", FG)])
    root.option_add("*TCombobox*Listbox.background", BG_INPUT)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 8, 0, 0))
    style.configure("TNotebook.Tab", background=BG_CARD, foreground=FG_MUTED,
                    padding=(16, 8), font=FONTS["body_bold"], borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", ACCENT)],
              foreground=[("selected", "#ffffff")])

    style.configure("Treeview", background=BG_CARD, fieldbackground=BG_CARD,
                    foreground=FG, rowheight=34, borderwidth=0, font=FONTS["body"])
    style.configure("Treeview.Heading", background=BG_SIDEBAR, foreground=FG_MUTED,
                    font=FONTS["small"], borderwidth=0, relief="flat", padding=(8, 6))
    style.map("Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", "#ffffff")])

    style.configure("TCheckbutton", background=BG_CARD, foreground=FG)
    style.map("TCheckbutton", background=[("active", BG_CARD)])

    style.configure("Vertical.TScrollbar", background=BG_CARD,
                    troughcolor=BG, arrowcolor=FG_MUTED, borderwidth=0)
    style.configure("Horizontal.TScrollbar", background=BG_CARD,
                    troughcolor=BG, arrowcolor=FG_MUTED, borderwidth=0)

    style.configure("Horizontal.TProgressbar", background=ACCENT,
                    troughcolor=BG_INPUT, borderwidth=0, lightcolor=ACCENT,
                    darkcolor=ACCENT)


class Card(ttk.Frame):
    """Rounded-ish flat card panel on the dark background."""

    def __init__(self, master, padding: int = 14, **kw):
        super().__init__(master, style="Card.TFrame", padding=padding, **kw)
        self.border = tk.Frame(self, bg=BORDER, bd=0, highlightthickness=1,
                               highlightbackground=BORDER)

    def pack_card(self, **kw):
        self.pack(**kw)
        return self


class Text(tk.Text):
    """Dark themed multiline text widget."""

    def __init__(self, master, **kw):
        kw.setdefault("bg", BG_INPUT)
        kw.setdefault("fg", FG)
        kw.setdefault("insertbackground", FG)
        kw.setdefault("relief", "flat")
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("highlightbackground", BORDER)
        kw.setdefault("font", FONTS["body"])
        kw.setdefault("wrap", "word")
        kw.setdefault("padx", 8)
        kw.setdefault("pady", 6)
        super().__init__(master, **kw)


class Pill(ttk.Label):
    """Small colored status/priority pill."""

    def __init__(self, master, text: str, color: str, **kw):
        super().__init__(master, text=f"  {text}  ", background=color,
                         foreground="#0b0f18" if color in (CYAN, AMBER, GREEN) else "#ffffff",
                         font=FONTS["small"], **kw)
