"""Settings view: organization / QMS configuration and data maintenance."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .. import database as db
from ..theme import (ACCENT, BG_CARD, BORDER, FG_MUTED, FONTS, RED)


class Settings(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="TFrame")
        self.app = app
        self._build()

    def _build(self):
        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x", padx=24, pady=(20, 10))
        ttk.Label(header, text="Settings", style="H1.TLabel").pack(side="left")

        card = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        card.pack(fill="x", padx=24, pady=(0, 16))
        inner = ttk.Frame(card, style="Card.TFrame", padding=20)
        inner.pack(fill="x")
        inner.columnconfigure(1, weight=1)

        self.vars: dict[str, tk.StringVar] = {}
        s = db.get_settings()
        fields = [
            ("company", "Organization name"),
            ("site", "Default site / facility"),
            ("qms_reference", "QMS procedure reference"),
            ("user", "Current user (shown on comments)"),
        ]
        for r, (key, label) in enumerate(fields):
            ttk.Label(inner, text=label, style="CardMuted.TLabel").grid(
                row=r, column=0, sticky="w", padx=(0, 14), pady=6)
            v = tk.StringVar(value=s.get(key, ""))
            self.vars[key] = v
            ttk.Entry(inner, textvariable=v).grid(row=r, column=1, sticky="we",
                                                  pady=6)

        btns = ttk.Frame(inner, style="Card.TFrame")
        btns.grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(14, 0))
        ttk.Button(btns, text="Save settings", style="Accent.TButton",
                   command=self.save).pack(side="left")

        # data section
        data_card = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER,
                             highlightthickness=1)
        data_card.pack(fill="x", padx=24)
        dinner = ttk.Frame(data_card, style="Card.TFrame", padding=20)
        dinner.pack(fill="x")
        ttk.Label(dinner, text="Data", style="CardH3.TLabel").pack(anchor="w")
        ttk.Label(dinner, text=f"Database file: {db.DB_PATH}",
                  style="CardMuted.TLabel").pack(anchor="w", pady=(4, 12))
        row = ttk.Frame(dinner, style="Card.TFrame")
        row.pack(anchor="w")
        ttk.Button(row, text="Export register CSV",
                   command=self.app.export_register).pack(side="left")
        ttk.Button(row, text="Reset demo data", style="Danger.TButton",
                   command=self.reset_data).pack(side="left", padx=8)

        about = ttk.Label(self, text="CAPA Desktop v1.0 — Corrective & Preventive "
                                     "Action management for quality systems.\n"
                                     "Built with Python + Tkinter. Data stays on this PC.",
                          style="Muted.TLabel", justify="left")
        about.pack(anchor="w", padx=26, pady=16)

    def save(self):
        for k, v in self.vars.items():
            db.set_setting(k, v.get().strip())
        self.app.toast("Settings saved")
        self.app.refresh_all()

    def reset_data(self):
        if messagebox.askyesno(
                "Reset demo data",
                "This deletes ALL CAPA records, tasks, comments and attachments on "
                "this computer and restores the sample dataset. Continue?",
                parent=self):
            conn = db.connect()
            try:
                conn.executescript(
                    "DELETE FROM documents; DELETE FROM events; DELETE FROM tasks;"
                    " DELETE FROM capa;")
                db._seed(conn)
                conn.commit()
            finally:
                conn.close()
            self.app.refresh_all()
            self.app.navigate("dashboard")
            self.app.toast("Demo data restored")
