"""CAPA Detail view: full record editor with tasks, attachments, activity."""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from datetime import date
from tkinter import filedialog, ttk, messagebox

from .. import database as db
from ..theme import (ACCENT, BG, BG_CARD, BG_INPUT, BORDER, FG, FG_MUTED, FONTS,
                     GREEN, RED, AMBER, STATUS_COLORS, PRIORITY_COLORS, Text)

SOURCES = ["Audit", "Complaint", "Deviation", "Inspection", "Nonconformance"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["Open", "In Progress", "Verification", "Closed"]
METHODS = ["", "5-Why", "Fishbone", "FMEA", "Is-Is Not", "8D", "Other"]


def today_iso() -> str:
    return date.today().isoformat()


class CapaDetail(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="TFrame")
        self.app = app
        self.capa_id: int | None = None
        self.entries: dict[str, tuple[ttk.Entry | ttk.Combobox, tk.StringVar]] = {}
        self.texts: dict[str, Text] = {}
        self._build()

    # ------------------------------------------------------------ layout
    def _build(self):
        top = ttk.Frame(self, style="TFrame")
        top.pack(fill="x", padx=24, pady=(16, 4))
        self.back_btn = ttk.Button(top, text="← Back", style="Ghost.TButton",
                                   command=lambda: self.app.navigate("register"))
        self.back_btn.pack(side="left")
        self.title_lbl = ttk.Label(top, text="CAPA Detail", style="H1.TLabel")
        self.title_lbl.pack(side="left", padx=14)
        self.status_pill = tk.Label(top, text="", width=14, font=FONTS["body_bold"],
                                    bg=BG, fg="#ffffff")
        self.status_pill.pack(side="right")
        ttk.Button(top, text="Save", style="Accent.TButton",
                   command=self.save).pack(side="right", padx=(0, 10))
        self.export_btn = ttk.Button(top, text="Export report",
                                     command=self.export_report)
        self.export_btn.pack(side="right", padx=(0, 8))
        self.delete_btn = ttk.Button(top, text="Delete", style="Danger.TButton",
                                     command=self.delete_capa)
        self.delete_btn.pack(side="right", padx=(0, 8))
        self.delete_btn.pack_forget()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=24, pady=(6, 16))
        self.nb = nb

        tab1 = ttk.Frame(nb, style="TFrame", padding=6)
        nb.add(tab1, text="  Record  ")
        self._build_record_tab(tab1)

        tab2 = ttk.Frame(nb, style="TFrame", padding=6)
        nb.add(tab2, text="  Root Cause & Actions  ")
        self._build_actions_tab(tab2)

        tab3 = ttk.Frame(nb, style="TFrame", padding=6)
        nb.add(tab3, text="  Tasks  ")
        self._build_tasks_tab(tab3)

        tab4 = ttk.Frame(nb, style="TFrame", padding=6)
        nb.add(tab4, text="  Attachments  ")
        self._build_docs_tab(tab4)

        tab5 = ttk.Frame(nb, style="TFrame", padding=6)
        nb.add(tab5, text="  Activity  ")
        self._build_activity_tab(tab5)

    def _field_row(self, parent, col, label, key, values=None, width=24):
        ttk.Label(parent, text=label, style="Muted.TLabel").grid(
            row=col // 2 * 2, column=col % 2 * 2, sticky="w", padx=(0, 6),
            pady=(8, 0))
        var = tk.StringVar()
        if values:
            e = ttk.Combobox(parent, textvariable=var, values=values, width=width,
                             state="readonly")
        else:
            e = ttk.Entry(parent, textvariable=var, width=width)
        e.grid(row=col // 2 * 2 + 1, column=col % 2 * 2, columnspan=2,
               sticky="we", padx=(0, 18))
        self.entries[key] = (e, var)

    def _text_block(self, parent, label, key, height=4):
        ttk.Label(parent, text=label, style="Muted.TLabel").pack(anchor="w",
                                                                 pady=(10, 2))
        t = Text(parent, height=height)
        t.pack(fill="x")
        self.texts[key] = t

    def _build_record_tab(self, parent):
        grid = ttk.Frame(parent, style="TFrame")
        grid.pack(fill="x")
        grid.columnconfigure((0, 2), weight=1, uniform="f")
        for i, (label, key, vals) in enumerate([
            ("Title", "title", None),
            ("Source", "source", SOURCES),
            ("Product / Area", "product", None),
            ("Site", "site", None),
            ("Originator", "originator", None),
            ("CAPA Owner", "owner", None),
            ("Priority", "priority", PRIORITIES),
            ("Status", "status", STATUSES),
            ("Opened on", "opened_on", None),
            ("Target completion date", "target_date", None),
            ("Closed on", "closed_on", None),
            ("Root cause method", "root_cause_method", METHODS),
        ]):
            self._field_row(grid, i, label, key, vals)
        self._text_block(parent, "Problem statement (what happened?)",
                         "problem_statement", 4)
        hint = ttk.Label(parent, text="Dates use YYYY-MM-DD (ISO) format.",
                         style="Muted.TLabel")
        hint.pack(anchor="w", pady=(6, 0))

    def _build_actions_tab(self, parent):
        wrap = ttk.Frame(parent, style="TFrame")
        wrap.pack(fill="both", expand=True)
        left = ttk.Frame(wrap, style="TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right = ttk.Frame(wrap, style="TFrame")
        right.pack(side="left", fill="both", expand=True)
        self._text_block(left, "Immediate containment", "containment", 6)
        self._text_block(left, "Root cause analysis result", "root_cause", 6)
        self._text_block(right, "Corrective action (addresses root cause)",
                         "corrective_action", 6)
        self._text_block(right, "Preventive action (stops recurrence elsewhere)",
                         "preventive_action", 5)
        self._text_block(right, "Effectiveness check plan", "effectiveness_check", 3)

    def _build_tasks_tab(self, parent):
        add = ttk.Frame(parent, style="TFrame")
        add.pack(fill="x", pady=(4, 8))
        self.task_desc = ttk.Entry(add, width=48)
        self.task_desc.pack(side="left", padx=(0, 6))
        self.task_assignee = ttk.Entry(add, width=20)
        self.task_assignee.pack(side="left", padx=(0, 6))
        self.task_due = ttk.Entry(add, width=12)
        self.task_due.pack(side="left", padx=(0, 6))
        ttk.Label(add, text="desc / assignee / due YYYY-MM-DD",
                  style="Muted.TLabel").pack(side="left")
        ttk.Button(add, text="Add task", command=self.add_task).pack(side="right")

        card = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        card.pack(fill="both", expand=True)
        self.tasks_canvas_frame = ttk.Frame(card, style="Card.TFrame")
        inner = tk.Canvas(card, bg=BG_CARD, highlightthickness=0)
        vsb = ttk.Scrollbar(card, orient="vertical", command=inner.yview)
        win = inner.create_window((0, 0), window=self.tasks_canvas_frame,
                                  anchor="nw")
        self.tasks_canvas_frame.bind(
            "<Configure>", lambda e: inner.configure(scrollregion=inner.bbox("all")))
        inner.bind("<Configure>", lambda e: inner.itemconfigure(win, width=e.width))
        inner.configure(yscrollcommand=vsb.set)
        inner.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        vsb.pack(side="right", fill="y")
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_lbl = ttk.Label(parent, text="", style="Muted.TLabel")
        self.progress_lbl.pack(anchor="w", pady=(6, 0))
        ttk.Progressbar(parent, variable=self.progress_var,
                        maximum=100).pack(fill="x", pady=(2, 0))

    def _build_docs_tab(self, parent):
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", pady=(4, 8))
        ttk.Button(bar, text="+ Attach file…", command=self.attach_file)\
            .pack(side="left")
        ttk.Button(bar, text="Remove selected", style="Danger.TButton",
                   command=self.remove_doc).pack(side="left", padx=8)
        self.doc_list = tk.Listbox(parent, bg=BG_INPUT, fg=FG,
                                   selectbackground=ACCENT, relief="flat",
                                   highlightthickness=1,
                                   highlightbackground=BORDER, font=FONTS["body"],
                                   activestyle="none")
        self.doc_list.pack(fill="both", expand=True)
        self.doc_list.bind("<Double-1>", self.open_doc)
        self.doc_ids: list[int] = []

    def _build_activity_tab(self, parent):
        self.activity_txt = Text(parent, height=20, state="disabled")
        self.activity_txt.pack(fill="both", expand=True)
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", pady=(8, 0))
        self.comment_entry = ttk.Entry(bar, width=70)
        self.comment_entry.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ttk.Button(bar, text="Post comment", style="Accent.TButton",
                   command=self.post_comment).pack(side="right")
        self.comment_entry.bind("<Return>", lambda e: self.post_comment())

    # ------------------------------------------------------------ load/save
    def load(self, capa_id: int):
        self.capa_id = capa_id
        row = db.get_capa(capa_id)
        if row is None:
            return
        number = row["capa_number"]
        self.title_lbl.configure(text=f"{number}")
        st = db.effective_status(row)
        color = STATUS_COLORS.get(st, FG_MUTED)
        self.status_pill.configure(text=f" {st} ", background=color,
                                   foreground="#0b0f18" if st in ("Open", "Verification", "Closed") else "#ffffff")
        self.delete_btn.pack(side="right", padx=(0, 8))
        mode = "disabled" if row["status"] == "Closed" else "normal"
        for key, (widget, var) in self.entries.items():
            var.set(row[key] or "")
            try:
                widget.configure(state="readonly" if isinstance(widget, ttk.Combobox) and mode == "normal"
                                 else ("disabled" if mode == "disabled" else "normal"))
                if not isinstance(widget, ttk.Combobox):
                    widget.configure(state=mode)
            except tk.TclError:
                pass
        for key, t in self.texts.items():
            t.configure(state="normal")
            t.delete("1.0", "end")
            t.insert("1.0", row[key] or "")
            if mode == "disabled":
                t.configure(state="disabled")
        self.refresh_tasks()
        self.refresh_docs()
        self.refresh_activity()

    def collect(self) -> dict:
        data = {k: v.get() for k, (_, v) in self.entries.items()}
        for k, t in self.texts.items():
            data[k] = t.get("1.0", "end").strip()
        return data

    def save(self, silent: bool = False) -> bool:
        if self.capa_id is None:
            return False
        data = self.collect()
        if not data.get("title"):
            messagebox.showwarning("Validation", "Title is required.", parent=self)
            return False
        for df in ("opened_on", "target_date"):
            try:
                date.fromisoformat(data[df])
            except ValueError:
                messagebox.showwarning(
                    "Validation", f"'{df.replace('_', ' ').capitalize()}' must be a "
                    "valid date in YYYY-MM-DD format.", parent=self)
                return False
        if data["status"] == "Closed" and not data.get("closed_on"):
            data["closed_on"] = today_iso()
        if data["status"] != "Closed":
            data["closed_on"] = ""
        db.update_capa(self.capa_id, data)
        if not silent:
            self.app.toast(f"{self.title_lbl['text']} saved")
            self.load(self.capa_id)
            self.app.refresh_all()
        return True

    # ------------------------------------------------------------ tasks
    def refresh_tasks(self):
        for w in self.tasks_canvas_frame.winfo_children():
            w.destroy()
        if self.capa_id is None:
            return
        tasks = db.list_tasks(self.capa_id)
        done = sum(1 for t in tasks if t["done"])
        total = len(tasks)
        self.progress_var.set(100 * done / total if total else 0)
        self.progress_lbl.configure(
            text=f"{done}/{total} action items complete")
        for t in tasks:
            row = tk.Frame(self.tasks_canvas_frame, bg=BG_CARD)
            row.pack(fill="x", pady=3)
            var = tk.BooleanVar(value=bool(t["done"]))
            cb = tk.Checkbutton(row, variable=var, bg=BG_CARD, activebackground=BG_CARD,
                                selectcolor=BG_INPUT, command=lambda tid=t["id"], v=var:
                                (db.toggle_task(tid, v.get()), self.refresh_tasks()))
            cb.pack(side="left")
            overdue = (not t["done"]) and t["due_date"] and t["due_date"] < today_iso()
            fg = RED if overdue else (FG_MUTED if t["done"] else FG)
            lbl = tk.Label(row, text=t["description"], bg=BG_CARD, fg=fg,
                           font=FONTS["body"], anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=6)
            tk.Label(row, text=f"{t['assignee'] or '-'}   ·   {t['due_date'] or 'no due date'}",
                     bg=BG_CARD, fg=RED if overdue else FG_MUTED,
                     font=FONTS["small"]).pack(side="left")
            tk.Button(row, text="✕", bg=BG_CARD, fg=FG_MUTED, bd=0,
                      activebackground=BG_CARD, activeforeground=RED,
                      command=lambda tid=t["id"]: (db.delete_task(tid),
                                                   self.refresh_tasks())).pack(side="left", padx=4)

    def add_task(self):
        if self.capa_id is None:
            return
        desc = self.task_desc.get().strip()
        if not desc:
            return
        db.add_task(self.capa_id, desc, self.task_assignee.get().strip(),
                    self.task_due.get().strip())
        self.task_desc.delete(0, "end")
        self.refresh_tasks()

    # ------------------------------------------------------------ docs
    def refresh_docs(self):
        self.doc_list.delete(0, "end")
        self.doc_ids = []
        if self.capa_id is None:
            return
        for d in db.list_documents(self.capa_id):
            self.doc_list.insert("end", f"  📎  {d['name']}     (added {d['added_on']})")
            self.doc_ids.append(d["id"])

    def attach_file(self):
        if self.capa_id is None:
            return
        paths = filedialog.askopenfilenames(title="Attach documents to this CAPA",
                                            parent=self)
        for p in paths:
            db.add_document(self.capa_id, os.path.basename(p), p)
        self.refresh_docs()

    def remove_doc(self):
        sel = self.doc_list.curselection()
        if sel:
            db.delete_document(self.doc_ids[sel[0]])
            self.refresh_docs()

    def open_doc(self, event=None):
        sel = self.doc_list.curselection()
        if not sel:
            return
        did = self.doc_ids[sel[0]]
        conn = db.connect()
        try:
            row = conn.execute("SELECT path FROM documents WHERE id=?", (did,)).fetchone()
        finally:
            conn.close()
        if row and row["path"] and os.path.exists(row["path"]):
            if sys.platform.startswith("win"):
                os.startfile(row["path"])  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", row["path"]])
        else:
            messagebox.showinfo("Attachment",
                                "The linked file is not available on this machine.",
                                parent=self)

    # ------------------------------------------------------------ activity
    def refresh_activity(self):
        t = self.activity_txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        if self.capa_id is None:
            return
        for e in db.list_events(self.capa_id):
            kind_color = {"comment": FG, "status": AMBER}.get(e["kind"], FG)
            t.insert("end", f"{e['ts']}   ", "meta")
            t.insert("end", f"{e['author']}  ", "author")
            t.insert("end", f"{e['body']}\n\n",
                     ("status" if e["kind"] == "status" else "comment"))
        t.tag_configure("meta", foreground=FG_MUTED, font=FONTS["small"])
        t.tag_configure("author", foreground=ACCENT, font=FONTS["body_bold"])
        t.tag_configure("status", foreground=AMBER)
        t.configure(state="disabled")

    def post_comment(self):
        body = self.comment_entry.get().strip()
        if not body or self.capa_id is None:
            return
        author = db.get_settings().get("user", "You")
        db.add_comment(self.capa_id, author, body)
        self.comment_entry.delete(0, "end")
        self.refresh_activity()

    # ------------------------------------------------------------ misc
    def delete_capa(self):
        if self.capa_id is None:
            return
        if messagebox.askyesno("Delete CAPA",
                               "Delete this CAPA and all its records?", parent=self):
            db.delete_capa(self.capa_id)
            self.capa_id = None
            self.app.refresh_all()
            self.app.navigate("register")

    def export_report(self):
        if self.capa_id is None:
            return
        from ..reporting import export_capa_txt
        path = export_capa_txt(self.capa_id, parent=self)
        if path:
            self.app.toast(f"Report exported to {path}")
