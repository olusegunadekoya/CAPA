"""Dashboard view: KPI cards, status donut (canvas), priority bars, due-soon list."""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from .. import database as db
from ..theme import (ACCENT, AMBER, BG, BG_CARD, BORDER, CYAN, FG, FG_MUTED, FONTS,
                     GREEN, PURPLE, RED, STATUS_COLORS, PRIORITY_COLORS)


class Dashboard(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="TFrame")
        self.app = app
        self._build()

    # ------------------------------------------------------------ layout
    def _build(self):
        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x", padx=24, pady=(20, 8))
        ttk.Label(header, text="Quality Dashboard", style="H1.TLabel").pack(side="left")
        ttk.Button(header, text="+ New CAPA", style="Accent.TButton",
                   command=self.app.new_capa).pack(side="right")
        settings = db.get_settings()
        ttk.Label(header, text=f"{settings.get('company', '')}  ·  {settings.get('site', '')}",
                  style="Muted.TLabel").pack(side="left", padx=16, pady=(10, 0))

        body = ttk.Frame(self, style="TFrame")
        body.pack(fill="both", expand=True, padx=24, pady=(4, 20))
        body.rowconfigure(2, weight=1)

        # ---- KPI cards row
        self.kpi_cards: dict[str, tuple[ttk.Frame, ttk.Label, ttk.Label]] = {}
        kpis = [
            ("total", "Total CAPAs", ACCENT),
            ("open", "Open", CYAN),
            ("in_progress", "In Progress", ACCENT),
            ("verification", "Verification", AMBER),
            ("overdue", "Overdue", RED),
            ("closed_this_month", "Closed This Month", GREEN),
        ]
        body.columnconfigure((0, 1, 2), weight=1, uniform="kpi")
        for i, (key, label, color) in enumerate(kpis[:3]):
            self._kpi(body, i, 0, key, label, color)
        for i, (key, label, color) in enumerate(kpis[3:]):
            self._kpi(body, i, 1, key, label, color)

        # ---- middle row: donut + priority bars
        charts = ttk.Frame(body, style="TFrame")
        charts.grid(row=2, column=0, columnspan=3, sticky="nsew")
        charts.columnconfigure(0, weight=3, uniform="c")
        charts.columnconfigure(1, weight=2, uniform="c")
        charts.rowconfigure(0, weight=1)

        donut_card = tk.Frame(charts, bg=BG_CARD, highlightbackground=BORDER,
                              highlightthickness=1)
        donut_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        ttk.Label(donut_card, text="CAPAs by Status", style="CardH3.TLabel",
                  padding=(14, 12, 14, 0)).pack(anchor="w")
        self.donut = tk.Canvas(donut_card, bg=BG_CARD, highlightthickness=0)
        self.donut.pack(fill="both", expand=True, padx=10, pady=6)

        right = ttk.Frame(charts, style="TFrame")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=10)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        prio_card = tk.Frame(right, bg=BG_CARD, highlightbackground=BORDER,
                             highlightthickness=1)
        prio_card.grid(row=0, column=0, sticky="nsew", pady=(10, 5))
        ttk.Label(prio_card, text="By Priority", style="CardH3.TLabel",
                  padding=(14, 10, 14, 4)).pack(anchor="w")
        self.prio_frame = tk.Frame(prio_card, bg=BG_CARD)
        self.prio_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        src_card = tk.Frame(right, bg=BG_CARD, highlightbackground=BORDER,
                            highlightthickness=1)
        src_card.grid(row=1, column=0, sticky="nsew", pady=(5, 10))
        ttk.Label(src_card, text="By Source", style="CardH3.TLabel",
                  padding=(14, 10, 14, 4)).pack(anchor="w")
        self.src_frame = tk.Frame(src_card, bg=BG_CARD)
        self.src_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        # ---- bottom: due soon table
        due_card = tk.Frame(body, bg=BG_CARD, highlightbackground=BORDER,
                            highlightthickness=1)
        due_card.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
        body.rowconfigure(3, weight=2)
        head = ttk.Frame(due_card, style="TFrame")
        head.pack(fill="x", padx=14, pady=(10, 4))
        ttk.Label(head, text="Due Soon & Overdue", style="CardH3.TLabel").pack(side="left")
        ttk.Button(head, text="Open register →", style="Ghost.TButton",
                   command=lambda: self.app.navigate("register")).pack(side="right")
        cols = ("capa", "title", "owner", "status", "target")
        self.due_tree = ttk.Treeview(due_card, columns=cols, show="headings",
                                     height=6)
        widths = {"capa": 110, "title": 380, "owner": 120, "status": 110, "target": 110}
        for c in cols:
            self.due_tree.heading(c, text={"capa": "CAPA #", "title": "Title",
                                           "owner": "Owner", "status": "Status",
                                           "target": "Target date"}[c])
            self.due_tree.column(c, width=widths[c],
                                 anchor="w" if c == "title" else "center")
        self.due_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.due_tree.tag_configure("overdue", foreground=RED)
        self.due_tree.tag_configure("soon", foreground=AMBER)
        self.due_tree.bind("<Double-1>",
                           lambda e: self._open_selected(self.due_tree))
        for t in (self.due_tree,):
            t.bind("<Return>", lambda e: self._open_selected(e.widget))

    def _kpi(self, parent, col, row, key, label, color):
        card = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        card.grid(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 10, 0),
                  pady=(10, 5))
        bar = tk.Frame(card, bg=color, width=4)
        bar.pack(side="left", fill="y")
        inner = ttk.Frame(card, style="Card.TFrame", padding=(14, 10))
        inner.pack(side="left", fill="both", expand=True)
        num = ttk.Label(inner, text="0", style="StatNum.TLabel", foreground=color)
        num.pack(anchor="w")
        lbl = ttk.Label(inner, text=label, style="CardMuted.TLabel")
        lbl.pack(anchor="w")
        self.kpi_cards[key] = (card, num, lbl)

    # ------------------------------------------------------------ refresh
    def refresh(self):
        m = db.metrics()
        for key, (_, num, _) in self.kpi_cards.items():
            num.configure(text=str(m.get(key, 0)))
        rows = db.list_capas()
        self._draw_donut(rows)
        self._draw_bars(self.prio_frame, "priority", ["Critical", "High", "Medium", "Low"],
                        PRIORITY_COLORS, rows)
        self._draw_bars(self.src_frame, "source",
                        ["Audit", "Complaint", "Deviation", "Inspection", "Nonconformance"],
                        {"Audit": PURPLE, "Complaint": RED, "Deviation": AMBER,
                         "Inspection": CYAN, "Nonconformance": GREEN}, rows)
        self._fill_due(rows)

    def _fill_due(self, rows):
        tree = self.due_tree
        tree.delete(*tree.get_children())
        active = [r for r in rows if r["status"] != "Closed"]
        active.sort(key=lambda r: r["target_date"])
        for r in active[:8]:
            days = db.days_remaining(r)
            st = db.effective_status(r)
            tag = "overdue" if st == "Overdue" else ("soon" if days is not None and days <= 7 else "")
            suffix = "" if days is None else (f" ({abs(days)}d late)" if days < 0 else f" (in {days}d)")
            tree.insert("", "end", iid=str(r["id"]),
                        values=(r["capa_number"], r["title"], r["owner"], st,
                                r["target_date"] + suffix),
                        tags=(tag,))

    def _open_selected(self, tree):
        sel = tree.selection()
        if sel:
            self.app.open_capa(int(sel[0]))

    # ------------------------------------------------------------ donut
    def _draw_donut(self, rows):
        c = self.donut
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20 or h < 20:
            c.after(80, lambda: self._draw_donut(rows))
            return
        counts = {}
        for r in rows:
            st = db.effective_status(r)
            counts[st] = counts.get(st, 0) + 1
        total = sum(counts.values()) or 1
        cx, cy = w * 0.34, h / 2
        radius = min(w * 0.28, h * 0.40)
        start = -90.0
        order = ["Open", "In Progress", "Verification", "Overdue", "Closed"]
        legend_x = w * 0.62
        legend_y = h / 2 - len(order) * 11
        for st in order:
            n = counts.get(st, 0)
            color = STATUS_COLORS.get(st, FG_MUTED)
            if n == 0:
                continue
            extent = 360.0 * n / total
            c.create_arc(cx - radius, cy - radius, cx + radius, cy + radius,
                         start=start, extent=extent, style="arc", width=22, outline=color)
            start += extent
        c.create_text(cx, cy - 8, text=str(total), fill=FG, font=FONTS["h2"])
        c.create_text(cx, cy + 14, text="total", fill=FG_MUTED, font=FONTS["small"])
        for st in order:
            n = counts.get(st, 0)
            color = STATUS_COLORS.get(st, FG_MUTED)
            c.create_rectangle(legend_x, legend_y - 5, legend_x + 12, legend_y + 7,
                               fill=color, outline="")
            c.create_text(legend_x + 20, legend_y, anchor="w", fill=FG,
                          font=FONTS["body"], text=f"{st}")
            c.create_text(legend_x + 150, legend_y, anchor="e", fill=FG_MUTED,
                          font=FONTS["body"], text=str(n))
            legend_y += 22

    # ------------------------------------------------------------ bars
    def _draw_bars(self, frame, field, order, colors, rows):
        for w in frame.winfo_children():
            w.destroy()
        counts = {k: 0 for k in order}
        for r in rows:
            v = r[field]
            if v in counts:
                counts[v] += 1
        max_n = max(list(counts.values()) + [1])
        for name in order:
            row = tk.Frame(frame, bg=BG_CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=name, width=14, anchor="w", bg=BG_CARD, fg=FG_MUTED,
                     font=FONTS["small"]).pack(side="left")
            track = tk.Frame(row, bg="#111726")
            track.pack(side="left", fill="x", expand=True, padx=(6, 6), ipady=4)
            frac = counts[name] / max_n
            bar = tk.Frame(track, bg=colors.get(name, ACCENT),
                           width=max(2, int(frac * 200)))
            bar.pack(side="left", fill="x")
            tk.Label(row, text=str(counts[name]), width=3, bg=BG_CARD, fg=FG,
                     font=FONTS["body_bold"]).pack(side="left")
