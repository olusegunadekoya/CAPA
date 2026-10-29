"""CAPA Register view: searchable / filterable / sortable table."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .. import database as db
from ..theme import (AMBER, BG, BG_CARD, BORDER, FG, FG_MUTED, FONTS, GREEN, RED,
                     STATUS_COLORS, PRIORITY_COLORS)

SORT_OPTIONS = {
    "Target date ↑": "target_date ASC",
    "Target date ↓": "target_date DESC",
    "Opened (newest)": "opened_on DESC",
    "CAPA #": "capa_number ASC",
    "Status": "status ASC",
}


class Register(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="TFrame")
        self.app = app
        self._build()

    def _build(self):
        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x", padx=24, pady=(20, 6))
        ttk.Label(header, text="CAPA Register", style="H1.TLabel").pack(side="left")
        ttk.Button(header, text="+ New CAPA", style="Accent.TButton",
                   command=self.app.new_capa).pack(side="right")

        filters = ttk.Frame(self, style="TFrame")
        filters.pack(fill="x", padx=24, pady=(2, 8))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        search = ttk.Entry(filters, textvariable=self.search_var, width=34)
        search.pack(side="left")
        search.insert(0, "")
        placeholder_hint = ttk.Label(filters, text="Search #, title, product, owner…   ",
                                     style="Muted.TLabel")
        placeholder_hint.pack(side="left")

        self.status_vars: dict[str, tk.BooleanVar] = {}
        status_box = ttk.Frame(filters, style="TFrame")
        status_box.pack(side="left", padx=(6, 10))
        for st in ["Open", "In Progress", "Verification", "Closed"]:
            v = tk.BooleanVar(value=True)
            self.status_vars[st] = v
            cb = ttk.Checkbutton(status_box, text=st, variable=v,
                                 command=self.refresh)
            cb.pack(side="left", padx=2)

        self.prio_vars: dict[str, tk.BooleanVar] = {}
        prio_box = ttk.Frame(filters, style="TFrame")
        prio_box.pack(side="left", padx=(0, 10))
        for p in ["Critical", "High", "Medium", "Low"]:
            v = tk.BooleanVar(value=True)
            self.prio_vars[p] = v
            ttk.Checkbutton(prio_box, text=p, variable=v,
                            command=self.refresh).pack(side="left", padx=2)

        self.sort_var = tk.StringVar(value="Target date ↑")
        ttk.Combobox(filters, textvariable=self.sort_var, state="readonly",
                     values=list(SORT_OPTIONS), width=15).pack(side="left")
        self.sort_var.trace_add("write", lambda *_: self.refresh())

        # ---- table
        card = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        card.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        cols = ("capa", "title", "source", "product", "owner", "priority",
                "status", "opened", "target", "days")
        headers = {"capa": "CAPA #", "title": "Title", "source": "Source",
                   "product": "Product / Area", "owner": "Owner",
                   "priority": "Priority", "status": "Status",
                   "opened": "Opened", "target": "Target", "days": "Days"}
        widths = {"capa": 110, "title": 300, "source": 110, "product": 190,
                  "owner": 100, "priority": 90, "status": 105, "opened": 90,
                  "target": 90, "days": 60}
        self.tree = ttk.Treeview(card, columns=cols, show="headings",
                                 selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c],
                             anchor="w" if c in ("title", "product") else "center",
                             stretch=(c in ("title", "product")))
        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", pady=8)

        for name, color in {**STATUS_COLORS, **PRIORITY_COLORS}.items():
            tag = f"st_{name.replace(' ', '_')}"
            self.tree.tag_configure(tag, foreground=color)
        self.tree.tag_configure("overdue", foreground=RED)

        self.tree.bind("<Double-1>", lambda e: self.open_selected())
        self.tree.bind("<Return>", lambda e: self.open_selected())
        self.tree.bind("<Delete>", lambda e: self.delete_selected())

        actions = ttk.Frame(self, style="TFrame")
        actions.pack(fill="x", padx=24, pady=(0, 14))
        ttk.Button(actions, text="Open selected", style="Accent.TButton",
                   command=self.open_selected).pack(side="left")
        ttk.Button(actions, text="Delete selected", style="Danger.TButton",
                   command=self.delete_selected).pack(side="left", padx=8)
        self.count_lbl = ttk.Label(actions, text="", style="Muted.TLabel")
        self.count_lbl.pack(side="right")

    # ------------------------------------------------------------ logic
    def refresh(self):
        statuses = "|".join(k for k, v in self.status_vars.items() if v.get())
        prios = "|".join(k for k, v in self.prio_vars.items() if v.get())
        rows = db.list_capas(search=self.search_var.get().strip(),
                             status=statuses, priority=prios,
                             order_by=SORT_OPTIONS[self.sort_var.get()])
        tree = self.tree
        tree.delete(*tree.get_children())
        overdue_count = 0
        for r in rows:
            st = db.effective_status(r)
            days = db.days_remaining(r)
            tags = []
            if st == "Overdue":
                tags.append("overdue")
                overdue_count += 1
            else:
                tags.append(f"st_{st.replace(' ', '_')}")
            tags.append(f"st_{r['priority'].replace(' ', '_')}")
            days_txt = "-" if st == "Closed" else \
                ("" if days is None else (f"{days}" if days >= 0 else f"{days} !"))
            tree.insert("", "end", iid=str(r["id"]),
                        values=(r["capa_number"], r["title"], r["source"],
                                r["product"], r["owner"], r["priority"], st,
                                r["opened_on"], r["target_date"], days_txt),
                        tags=tuple(tags))
        txt = f"{len(rows)} CAPAs shown"
        if overdue_count:
            txt += f"  ·  {overdue_count} overdue"
        self.count_lbl.configure(text=txt,
                                 foreground=RED if overdue_count else FG_MUTED)

    def open_selected(self):
        sel = self.tree.selection()
        if sel:
            self.app.open_capa(int(sel[0]))

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        cid = int(sel[0])
        row = db.get_capa(cid)
        if messagebox.askyesno(
                "Delete CAPA",
                f"Delete {row['capa_number']} — {row['title']}?\n"
                "This removes all tasks, comments and documents. This cannot be undone.",
                parent=self):
            db.delete_capa(cid)
            self.refresh()
            self.app.refresh_all()
