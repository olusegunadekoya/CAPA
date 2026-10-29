"""Reporting helpers: export a single CAPA record or the full register.

The core builders (``capa_to_text`` / ``register_csv_text``) are GUI-free so
the web server can reuse them; the ``export_*`` wrappers add the Tkinter
save-file dialogs used by the desktop app.
"""
from __future__ import annotations

import csv
import io
import os
from datetime import datetime

from . import database as db
from .database import data_dir

SECTIONS = [
    ("Problem statement", "problem_statement"),
    ("Immediate containment", "containment"),
    ("Root cause analysis method", "root_cause_method"),
    ("Root cause", "root_cause"),
    ("Corrective action", "corrective_action"),
    ("Preventive action", "preventive_action"),
    ("Effectiveness check", "effectiveness_check"),
]


def capa_to_text(capa_id: int) -> str:
    row = db.get_capa(capa_id)
    if row is None:
        return ""
    s = db.get_settings()
    lines = []
    bar = "=" * 78
    lines.append(bar)
    lines.append(f"{s.get('company', '')} — CORRECTIVE AND PREVENTIVE ACTION (CAPA) RECORD")
    lines.append(f"Reference: {s.get('qms_reference', '')}")
    lines.append(bar)
    lines.append("")
    lines.append(f"CAPA number      : {row['capa_number']}")
    lines.append(f"Title            : {row['title']}")
    lines.append(f"Source           : {row['source']}")
    lines.append(f"Product / Area   : {row['product']}")
    lines.append(f"Site             : {row['site']}")
    lines.append(f"Originator       : {row['originator']}")
    lines.append(f"CAPA owner       : {row['owner']}")
    lines.append(f"Priority         : {row['priority']}")
    lines.append(f"Status           : {db.effective_status(row)}")
    lines.append(f"Opened on        : {row['opened_on']}")
    lines.append(f"Target date      : {row['target_date']}")
    if row["closed_on"]:
        lines.append(f"Closed on        : {row['closed_on']}")
    lines.append(f"Report generated : {datetime.now():%Y-%m-%d %H:%M}")
    lines.append("")
    for label, key in SECTIONS:
        val = (row[key] or "").strip() or "[not completed]"
        lines.append("-" * 78)
        lines.append(label.upper())
        lines.append("-" * 78)
        lines.append(val)
        lines.append("")
    tasks = db.list_tasks(capa_id)
    lines.append("-" * 78)
    lines.append("ACTION ITEM TASKS")
    lines.append("-" * 78)
    if tasks:
        for t in tasks:
            mark = "x" if t["done"] else " "
            lines.append(f"[{mark}] {t['description']}  "
                         f"(owner: {t['assignee'] or '-'}; due: {t['due_date'] or '-'})")
    else:
        lines.append("[none]")
    lines.append("")
    docs = db.list_documents(capa_id)
    if docs:
        lines.append("-" * 78)
        lines.append("ATTACHED DOCUMENTS")
        lines.append("-" * 78)
        for d in docs:
            lines.append(f"- {d['name']} (added {d['added_on']})")
        lines.append("")
    events = db.list_events(capa_id)
    if events:
        lines.append("-" * 78)
        lines.append("ACTIVITY LOG")
        lines.append("-" * 78)
        for e in reversed(events):
            lines.append(f"{e['ts']}  {e['author']}: {e['body']}")
        lines.append("")
    lines.append(bar)
    lines.append("Electronic record produced by CAPA Desktop. "
                 "Review and approval per QMS procedures.")
    lines.append(bar)
    return "\n".join(lines)


def register_csv_text() -> str:
    """Build the full-register CSV as a string (GUI-free, shared with web)."""
    rows = db.list_capas(order_by="capa_number ASC")
    fields = ["capa_number", "title", "source", "product", "site", "originator",
              "owner", "priority", "status", "opened_on", "target_date", "closed_on"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(fields + ["effective_status", "days_remaining"])
    for r in rows:
        days = db.days_remaining(r)
        w.writerow([r[k] for k in fields] + [db.effective_status(r),
                                             "" if days is None else days])
    return buf.getvalue()


def export_capa_txt(capa_id: int, parent=None) -> str | None:
    from tkinter import filedialog
    row = db.get_capa(capa_id)
    if row is None:
        return None
    text = capa_to_text(capa_id)
    path = filedialog.asksaveasfilename(
        parent=parent, title="Export CAPA report",
        initialfile=f"{row['capa_number'].replace('/', '-')}_report.txt",
        defaultextension=".txt",
        filetypes=[("Text document", "*.txt"), ("All files", "*.*")])
    if not path:
        return None
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def export_register_csv(parent=None) -> str | None:
    from tkinter import filedialog
    path = filedialog.asksaveasfilename(
        parent=parent, title="Export CAPA register",
        initialfile=f"CAPA_register_{datetime.now():%Y%m%d}.csv",
        defaultextension=".csv",
        filetypes=[("CSV file", "*.csv"), ("All files", "*.*")])
    if not path:
        return None
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        f.write(register_csv_text())
    return path
