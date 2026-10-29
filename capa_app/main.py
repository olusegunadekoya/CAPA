"""CAPA Desktop — main application window.

A quality-management desktop app for tracking Corrective and Preventive
Actions (CAPA) on Windows PCs. Pure Python standard library (Tkinter + SQLite).
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

# Support running both as `python -m capa_app` and `python main.py`
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from capa_app import database as db
    from capa_app.theme import (ACCENT, BG, BG_CARD, BG_SIDEBAR, BORDER, FG,
                                FG_MUTED, FONTS, apply_styles)
    from capa_app.reporting import export_register_csv
    from capa_app.new_capa_dialog import NewCapaDialog
    from capa_app.views.dashboard import Dashboard
    from capa_app.views.register import Register
    from capa_app.views.detail import CapaDetail
    from capa_app.views.tasks import MyTasks
    from capa_app.views.settings import Settings
else:
    from . import database as db
    from .theme import (ACCENT, BG, BG_CARD, BG_SIDEBAR, BORDER, FG, FG_MUTED,
                        FONTS, apply_styles)
    from .reporting import export_register_csv
    from .new_capa_dialog import NewCapaDialog
    from .views.dashboard import Dashboard
    from .views.register import Register
    from .views.detail import CapaDetail
    from .views.tasks import MyTasks
    from .views.settings import Settings

APP_TITLE = "CAPA Desktop — Corrective & Preventive Action"

NAV_ITEMS = [
    ("dashboard", "⌂   Dashboard"),
    ("register", "☰   CAPA Register"),
    ("tasks", "✓   My Tasks"),
    ("settings", "⚙   Settings"),
]


class CapaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        db.init_db()
        self.title(APP_TITLE)
        self.geometry("1280x800")
        self.minsize(1024, 680)
        apply_styles(self)
        try:
            self.iconname("CAPA")
        except tk.TclError:
            pass

        self._build_shell()
        self._build_views()
        self.navigate("dashboard")
        self.bind_all("<Control-n>", lambda e: self.new_capa())
        self.bind_all("<Control-f>", lambda e: (self.navigate("register"),))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------ shell
    def _build_shell(self):
        outer = ttk.Frame(self, style="TFrame")
        outer.pack(fill="both", expand=True)

        sidebar = ttk.Frame(outer, style="Sidebar.TFrame", width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        logo = tk.Frame(sidebar, bg=BG_SIDEBAR)
        logo.pack(fill="x", padx=18, pady=(22, 14))
        badge = tk.Canvas(logo, width=38, height=38, bg=BG_SIDEBAR,
                          highlightthickness=0)
        badge.create_oval(2, 2, 36, 36, fill=ACCENT, outline="")
        badge.create_text(19, 19, text="C", fill="#ffffff",
                          font=("Segoe UI", 17, "bold"))
        badge.pack(side="left")
        txt = tk.Frame(logo, bg=BG_SIDEBAR)
        txt.pack(side="left", padx=(10, 0))
        tk.Label(txt, text="CAPA", bg=BG_SIDEBAR, fg=FG,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(txt, text="Quality Desktop", bg=BG_SIDEBAR, fg=FG_MUTED,
                 font=FONTS["small"]).pack(anchor="w")

        self.nav_buttons: dict[str, tk.Frame] = {}
        nav = tk.Frame(sidebar, bg=BG_SIDEBAR)
        nav.pack(fill="x", padx=10, pady=4)
        for key, label in NAV_ITEMS:
            btn = tk.Frame(nav, bg=BG_SIDEBAR, cursor="hand2")
            btn.pack(fill="x", pady=2)
            lbl = tk.Label(btn, text=label, bg=BG_SIDEBAR, fg=FG_MUTED,
                           font=FONTS["nav"], anchor="w", padx=12, pady=9)
            lbl.pack(fill="x")
            marker = tk.Frame(btn, bg=ACCENT, width=3)
            btn.bind("<Button-1>", lambda e, k=key: self.navigate(k))
            lbl.bind("<Button-1>", lambda e, k=key: self.navigate(k))
            btn._label = lbl  # type: ignore[attr-defined]
            btn._marker = marker  # type: ignore[attr-defined]
            self.nav_buttons[key] = btn

        new_btn = ttk.Button(sidebar, text="+  New CAPA", style="Accent.TButton",
                             command=self.new_capa)
        new_btn.pack(fill="x", padx=16, pady=(18, 6))

        s = db.get_settings()
        foot = tk.Frame(sidebar, bg=BG_SIDEBAR)
        foot.pack(side="bottom", fill="x", padx=18, pady=(0, 16))
        tk.Label(foot, text=s.get("company", ""), bg=BG_SIDEBAR, fg=FG,
                 font=FONTS["body_bold"], wraplength=180,
                 justify="left").pack(anchor="w")
        tk.Label(foot, text=s.get("site", ""), bg=BG_SIDEBAR, fg=FG_MUTED,
                 font=FONTS["small"], wraplength=180, justify="left").pack(anchor="w")
        self.sidebar_foot = foot

        self.main = tk.Frame(outer, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        self.toast_lbl = tk.Label(self.main, text="", bg="#0b0f18", fg="#ffffff",
                                  font=FONTS["body"], padx=14, pady=8)

    def _build_views(self):
        self.views: dict[str, ttk.Frame] = {}
        self.dashboard = Dashboard(self.main, self)
        self.register = Register(self.main, self)
        self.detail = CapaDetail(self.main, self)
        self.tasks = MyTasks(self.main, self)
        self.settings = Settings(self.main, self)
        for k, v in [("dashboard", self.dashboard), ("register", self.register),
                     ("detail", self.detail), ("tasks", self.tasks),
                     ("settings", self.settings)]:
            self.views[k] = v

    # ------------------------------------------------------------ nav
    def navigate(self, key: str):
        if key not in self.views:
            return
        for k, btn in self.nav_buttons.items():
            active = (k == key) or (k == "register" and key == "detail")
            btn.configure(bg=BG_CARD if active else BG_SIDEBAR)
            btn._label.configure(bg=BG_CARD if active else BG_SIDEBAR,
                                 fg=FG if active else FG_MUTED,
                                 font=FONTS["nav_active"] if active else FONTS["nav"])
            if active:
                btn._marker.pack(side="left", fill="y")
            else:
                btn._marker.pack_forget()
        view = self.views[key]
        for v in self.views.values():
            v.place_forget()
        view.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        refresh = getattr(view, "refresh", None)
        if refresh:
            refresh()

    def open_capa(self, capa_id: int):
        self.detail.load(capa_id)
        self.navigate("detail")

    def new_capa(self):
        NewCapaDialog(self, on_created=lambda cid: self.open_capa(cid))

    def export_register(self):
        path = export_register_csv(parent=self)
        if path:
            self.toast(f"Register exported to {path}")

    def refresh_all(self):
        self.dashboard.refresh()
        self.register.refresh()
        self.tasks.refresh()
        s = db.get_settings()
        for w in self.sidebar_foot.winfo_children():
            w.destroy()
        tk.Label(self.sidebar_foot, text=s.get("company", ""), bg=BG_SIDEBAR,
                 fg=FG, font=FONTS["body_bold"], wraplength=180,
                 justify="left").pack(anchor="w")
        tk.Label(self.sidebar_foot, text=s.get("site", ""), bg=BG_SIDEBAR,
                 fg=FG_MUTED, font=FONTS["small"], wraplength=180,
                 justify="left").pack(anchor="w")

    # ------------------------------------------------------------ toast
    def toast(self, msg: str):
        self.toast_lbl.configure(text=msg)
        self.toast_lbl.place(relx=0.5, rely=0.94, anchor="s")
        after = getattr(self, "_toast_after", None)
        if after:
            self.after_cancel(after)
        self._toast_after = self.after(2600, self.toast_lbl.place_forget)

    def _on_close(self):
        self.destroy()


def main():
    app = CapaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
