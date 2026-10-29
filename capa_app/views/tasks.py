"""My Tasks view: all action items across CAPAs, grouped by owner / overdue."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk

from .. import database as db
from ..theme import (ACCENT, BG, BG_CARD, BORDER, FG, FG_MUTED, FONTS, GREEN, RED, AMBER)


class MyTasks(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="TFrame")
        self.app = app
        self._build()

    def _build(self):
        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x", padx=24, pady=(20, 8))
        ttk.Label(header, text="My Tasks", style="H1.TLabel").pack(side="left")
        ttk.Button(header, text="Export register CSV",
                   command=self.app.export_register).pack(side="right")

        legend = ttk.Frame(self, style="TFrame")
        legend.pack(fill="x", padx=24)
        for txt, color in [("Overdue", RED), ("Due within 7 days", AMBER),
                           ("Upcoming", FG_MUTED), ("Completed", GREEN)]:
            dot = tk.Canvas(legend, width=10, height=10, bg=BG, highlightthickness=0)
            dot.create_oval(1, 1, 9, 9, fill=color, outline="")
            dot.pack(side="left", padx=(12, 4))
            ttk.Label(legend, text=txt, style="Muted.TLabel").pack(side="left")

        card = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        card.pack(fill="both", expand=True, padx=24, pady=(10, 20))
        inner = tk.Canvas(card, bg=BG_CARD, highlightthickness=0)
        vsb = ttk.Scrollbar(card, orient="vertical", command=inner.yview)
        self.list_frame = ttk.Frame(inner, style="Card.TFrame")
        win = inner.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>",
                             lambda e: inner.configure(scrollregion=inner.bbox("all")))
        inner.bind("<Configure>", lambda e: inner.itemconfigure(win, width=e.width))
        inner.configure(yscrollcommand=vsb.set)
        inner.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.summary = ttk.Label(self, text="", style="Muted.TLabel")
        self.summary.pack(anchor="w", padx=26, pady=(0, 10))

    def refresh(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        conn = db.connect()
        try:
            rows = conn.execute(
                "SELECT t.*, c.capa_number, c.title, c.status AS capa_status, c.priority "
                "FROM tasks t JOIN capa c ON c.id = t.capa_id "
                "ORDER BY t.done, t.due_date").fetchall()
        finally:
            conn.close()
        today = date.today().isoformat()
        overdue = soon = done = 0
        current_capa = None
        for r in rows:
            if r["capa_number"] != current_capa:
                current_capa = r["capa_number"]
                hdr = tk.Frame(self.list_frame, bg=BG_CARD)
                hdr.pack(fill="x", padx=10, pady=(10, 2))
                link = tk.Label(hdr, text=f"{r['capa_number']} — {r['title']}",
                                bg=BG_CARD, fg=ACCENT, font=FONTS["body_bold"],
                                cursor="hand2")
                link.pack(side="left")
                link.bind("<Button-1>",
                          lambda e, cid=r["capa_id"]: self.app.open_capa(cid))
                tk.Label(hdr, text=r["capa_status"], bg=BG_CARD, fg=FG_MUTED,
                         font=FONTS["small"]).pack(side="right")
            is_done = bool(r["done"])
            is_overdue = (not is_done) and r["due_date"] and r["due_date"] < today
            is_soon = (not is_done) and not is_overdue and r["due_date"] and \
                (date.fromisoformat(r["due_date"]) - date.today()).days <= 7
            if is_done:
                done += 1
            elif is_overdue:
                overdue += 1
            elif is_soon:
                soon += 1
            color = GREEN if is_done else (RED if is_overdue else
                                           (AMBER if is_soon else FG))
            row = tk.Frame(self.list_frame, bg=BG_CARD)
            row.pack(fill="x", padx=10, pady=2)
            var = tk.BooleanVar(value=is_done)
            cb = tk.Checkbutton(row, variable=var, bg=BG_CARD,
                                activebackground=BG_CARD, selectcolor="#232d42",
                                command=lambda tid=r["id"], v=var: self._toggle(tid, v))
            cb.pack(side="left")
            strike = ("Segoe UI", 10, "overstrike") if is_done else FONTS["body"]
            tk.Label(row, text=r["description"], bg=BG_CARD,
                     fg=FG_MUTED if is_done else color, font=strike,
                     anchor="w").pack(side="left", fill="x", expand=True, padx=6)
            tk.Label(row, text=r["assignee"] or "unassigned", bg=BG_CARD,
                     fg=FG_MUTED, font=FONTS["small"], width=22).pack(side="left")
            due_txt = r["due_date"] or "-"
            if is_overdue:
                due_txt += " ⚠"
            tk.Label(row, text=due_txt, width=13, bg=BG_CARD,
                     fg=FG_MUTED if is_done else color,
                     font=FONTS["small"]).pack(side="left")
        total = len(rows)
        self.summary.configure(
            text=f"{total} action items · {overdue} overdue · {soon} due soon · "
                 f"{done} completed",
            foreground=RED if overdue else FG_MUTED)
        if total == 0:
            tk.Label(self.list_frame, text="No tasks yet. Add action items inside a CAPA.",
                     bg=BG_CARD, fg=FG_MUTED, font=FONTS["body"]).pack(pady=24)

    def _toggle(self, task_id: int, var):
        db.toggle_task(task_id, var.get())
        self.refresh()
