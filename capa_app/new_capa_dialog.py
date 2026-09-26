"""Modal dialog for creating a new CAPA record."""
from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

from . import database as db
from .theme import (ACCENT, BG, BG_CARD, BORDER, FG, FG_MUTED, FONTS, Text)
from .views.detail import SOURCES, PRIORITIES, METHODS


class NewCapaDialog(tk.Toplevel):
    def __init__(self, master, on_created):
        super().__init__(master)
        self.title("New CAPA")
        self.configure(bg=BG)
        self.on_created = on_created
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        w, h = 560, 560
        x = master.winfo_rootx() + (master.winfo_width() - w) // 2
        y = master.winfo_rooty() + (master.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

        head = ttk.Frame(self, style="TFrame", padding=(20, 16, 20, 4))
        head.pack(fill="x")
        ttk.Label(head, text="Create new CAPA", style="H2.TLabel").pack(side="left")
        ttk.Label(head, text=f"Number: {db.next_capa_number()}",
                  style="Muted.TLabel").pack(side="right", pady=(7, 0))

        form = ttk.Frame(self, style="TFrame", padding=(20, 8))
        form.pack(fill="both", expand=True)
        form.columnconfigure((0, 1), weight=1, uniform="c")

        today = date.today()

        def add(key, label, values=None, default="", row=None, col=0, span=1):
            parent_row = row if row is not None else add_r[0]
            ttk.Label(form, text=label, style="Muted.TLabel").grid(
                row=parent_row * 2, column=col, sticky="w", padx=(0, 14))
            var = tk.StringVar(value=default)
            if values:
                e = ttk.Combobox(form, textvariable=var, values=values,
                                 state="readonly", width=22)
            else:
                e = ttk.Entry(form, textvariable=var, width=24)
            e.grid(row=parent_row * 2 + 1, column=col, columnspan=span,
                   sticky="we", padx=(0, 14), pady=(1, 7))
            vars_[key] = var
            return var

        vars_: dict[str, tk.StringVar] = {}
        add_r = [0]

        def grid_pair(label_a, key_a, label_b, key_b, va=None, vb=None, da="", db_=""):
            r = add_r[0]
            add(key_a, label_a, va, da, row=r, col=0)
            add(key_b, label_b, vb, db_, row=r, col=1)
            add_r[0] += 1

        grid_pair("Title *", "title", "Source", "source", None, SOURCES)
        grid_pair("Product / Area", "product", "Site", "site")
        grid_pair("Originator", "originator", "CAPA owner", "owner")
        grid_pair("Priority", "priority", "Root cause method", "root_cause_method",
                  PRIORITIES, METHODS, "Medium", "5-Why")
        grid_pair("Opened on", "opened_on", "Target completion", "target_date",
                  None, None, today.isoformat(),
                  (today + timedelta(days=30)).isoformat())

        ttk.Label(form, text="Problem statement", style="Muted.TLabel").grid(
            row=add_r[0] * 2, column=0, columnspan=2, sticky="w")
        problem = Text(form, height=6)
        problem.grid(row=add_r[0] * 2 + 1, column=0, columnspan=2, sticky="nsew",
                     pady=(1, 7))
        form.rowconfigure(add_r[0] * 2 + 1, weight=1)

        btns = ttk.Frame(self, style="TFrame", padding=(20, 6, 20, 18))
        btns.pack(fill="x")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")

        def create():
            data = {k: v.get().strip() for k, v in vars_.items()}
            if not data["title"]:
                from tkinter import messagebox
                messagebox.showwarning("Missing field", "Title is required.",
                                       parent=self)
                return
            try:
                date.fromisoformat(data["opened_on"])
                date.fromisoformat(data["target_date"])
            except ValueError:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Invalid date", "Dates must be YYYY-MM-DD.", parent=self)
                return
            data["status"] = "Open"
            data["containment"] = ""
            data["root_cause"] = ""
            data["corrective_action"] = ""
            data["preventive_action"] = ""
            data["effectiveness_check"] = ""
            data["closed_on"] = ""
            data["problem_statement"] = problem.get("1.0", "end").strip()
            cid = db.create_capa(data)
            self.destroy()
            self.on_created(cid)

        ttk.Button(btns, text="Create CAPA", style="Accent.TButton",
                   command=create).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda e: create())
        self.bind("<Escape>", lambda e: self.destroy())
