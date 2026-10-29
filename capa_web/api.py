"""JSON API used by the CAPA web front-end.

Every handler returns plain dicts / lists; the server serialises them to
JSON.  The module deliberately depends only on ``capa_app.database`` so the
web and desktop UIs share one source of truth.
"""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import date, datetime
from typing import Any, Optional

from capa_app import database as db
from capa_app import reporting

SOURCES = ["Audit", "Complaint", "Deviation", "Inspection", "Nonconformance"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["Open", "In Progress", "Verification", "Closed"]
RCA_METHODS = ["5-Why", "Fishbone", "FMEA", "Is-Is Not", "8D", "Other"]


class ApiError(Exception):
    """Raised for expected client errors -> HTTP 400/404."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# --------------------------------------------------------------- helpers

def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def capa_summary(row: sqlite3.Row) -> dict[str, Any]:
    days = db.days_remaining(row)
    return {
        "id": row["id"],
        "capa_number": row["capa_number"],
        "title": row["title"],
        "source": row["source"],
        "product": row["product"],
        "site": row["site"],
        "owner": row["owner"],
        "priority": row["priority"],
        "status": row["status"],
        "effective_status": db.effective_status(row),
        "opened_on": row["opened_on"],
        "target_date": row["target_date"],
        "closed_on": row["closed_on"],
        "days_remaining": days,
    }


_DATE_FIELDS = ("opened_on", "target_date", "closed_on")


def _validate(payload: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for field in db.CAPA_FIELDS:
        if field not in payload:
            if partial:
                continue
            data[field] = None
            continue
        value = payload.get(field)
        value = "" if value is None else str(value).strip()
        if field in _DATE_FIELDS and value:
            try:
                date.fromisoformat(value)
            except ValueError:
                raise ApiError(f"Invalid date in '{field}' (expected YYYY-MM-DD)")
        data[field] = value
    if not partial:
        if not data.get("title"):
            raise ApiError("Title is required")
        if not data.get("source"):
            raise ApiError("Source is required")
        if not data.get("opened_on"):
            data["opened_on"] = date.today().isoformat()
        if not data.get("target_date"):
            raise ApiError("Target date is required")
    # normalise enum-ish fields against known vocabularies
    if data.get("status") and data["status"] not in STATUSES:
        raise ApiError(f"Unknown status '{data['status']}'")
    if data.get("priority") and data["priority"] not in PRIORITIES:
        raise ApiError(f"Unknown priority '{data['priority']}'")
    return data


# ----------------------------------------------------------------- reads

def get_bootstrap() -> dict[str, Any]:
    return {
        "settings": db.get_settings(),
        "today": date.today().isoformat(),
        "vocab": {
            "sources": SOURCES,
            "priorities": PRIORITIES,
            "statuses": STATUSES,
            "rca_methods": RCA_METHODS,
        },
    }


def get_metrics() -> dict[str, Any]:
    m = db.metrics()
    rows = db.list_capas()
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_source: dict[str, int] = {}
    due_soon: list[dict[str, Any]] = []
    overdue: list[dict[str, Any]] = []
    for r in rows:
        st = db.effective_status(r)
        by_status[st] = by_status.get(st, 0) + 1
        by_priority[r["priority"]] = by_priority.get(r["priority"], 0) + 1
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
        days = db.days_remaining(r)
        item = capa_summary(r)
        if st == "Overdue":
            overdue.append(item)
        elif days is not None and 0 <= days <= 14:
            due_soon.append(item)
    overdue.sort(key=lambda x: x["target_date"])
    due_soon.sort(key=lambda x: x["target_date"])
    m["by_status"] = by_status
    m["by_priority"] = by_priority
    m["by_source"] = by_source
    m["due_soon"] = due_soon
    m["overdue_items"] = overdue     # list; scalar count stays in m["overdue"]
    m["completion_rate"] = round(100 * m["closed"] / m["total"]) if m["total"] else 0
    return m


def list_capas(query: dict[str, list[str]]) -> list[dict[str, Any]]:
    search = (query.get("search") or [""])[0]
    status = (query.get("status") or [""])[0]
    priority = (query.get("priority") or [""])[0]
    order_by = (query.get("order") or ["target_date ASC"])[0]
    if status == "Overdue":
        # derived state — filter after fetching (mirrors the desktop register)
        rows = db.list_capas(search=search, priority=priority, order_by=order_by)
        return [capa_summary(r) for r in rows if db.effective_status(r) == "Overdue"]
    rows = db.list_capas(search=search, status=status, priority=priority,
                         order_by=order_by)
    return [capa_summary(r) for r in rows]


def get_capa(capa_id: int) -> dict[str, Any]:
    row = db.get_capa(capa_id)
    if row is None:
        raise ApiError("CAPA not found", 404)
    detail = capa_summary(row)
    full = _row_dict(row)
    for k in db.CAPA_FIELDS:
        detail[k] = full.get(k, "")
    tasks = [_row_dict(t) for t in db.list_tasks(capa_id)]
    events = [_row_dict(e) for e in db.list_events(capa_id)]
    documents = [_row_dict(d) for d in db.list_documents(capa_id)]
    done = sum(1 for t in tasks if t["done"])
    detail.update({
        "tasks": tasks,
        "events": events,
        "documents": documents,
        "task_progress": {"done": done, "total": len(tasks)},
        "report_text": reporting.capa_to_text(capa_id),
    })
    return detail


def list_all_tasks() -> dict[str, Any]:
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT t.*, c.capa_number, c.title, c.status AS capa_status, "
            "c.priority FROM tasks t JOIN capa c ON c.id = t.capa_id "
            "ORDER BY t.done, t.due_date").fetchall()
    finally:
        conn.close()
    groups: dict[str, list[dict[str, Any]]] = {}
    counts = {"open": 0, "overdue": 0, "done": 0}
    today = date.today()
    for r in rows:
        g = f"{r['capa_number']} — {r['title']}"
        days = None
        state = "ok"
        if r["due_date"]:
            try:
                days = (date.fromisoformat(r["due_date"]) - today).days
            except ValueError:
                days = None
        if r["done"]:
            state = "done"
            counts["done"] += 1
        elif days is not None and days < 0:
            state = "overdue"
            counts["overdue"] += 1
        else:
            state = "open"
            counts["open"] += 1
        groups.setdefault(g, []).append({
            "id": r["id"], "capa_id": r["capa_id"],
            "description": r["description"], "assignee": r["assignee"],
            "due_date": r["due_date"], "done": bool(r["done"]),
            "days": days, "state": state,
            "capa_status": r["capa_status"], "priority": r["priority"],
        })
    return {"groups": [{"capa": k, "items": v} for k, v in groups.items()],
            "counts": counts}


# ---------------------------------------------------------------- writes

def create_capa(payload: dict[str, Any]) -> dict[str, Any]:
    data = _validate(payload)
    data["capa_number"] = payload.get("capa_number") or db.next_capa_number()
    if not data.get("originator"):
        data["originator"] = db.get_settings().get("user", "")
    cid = db.create_capa(data)
    return {"id": cid, "capa_number": data["capa_number"]}


def update_capa(capa_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    if db.get_capa(capa_id) is None:
        raise ApiError("CAPA not found", 404)
    data = _validate(payload, partial=True)
    # auto-fill closed_on when moving to Closed, clear it when re-opening
    if data.get("status") == "Closed":
        row = db.get_capa(capa_id)
        if not (payload.get("closed_on") or row["closed_on"]):
            data["closed_on"] = date.today().isoformat()
    elif "status" in data and data["status"] != "Closed":
        if payload.get("closed_on") is None:
            data["closed_on"] = ""
    db.update_capa(capa_id, data)
    return {"ok": True}


def delete_capa(capa_id: int) -> dict[str, Any]:
    if db.get_capa(capa_id) is None:
        raise ApiError("CAPA not found", 404)
    db.delete_capa(capa_id)
    return {"ok": True}


def add_comment(capa_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    body = str(payload.get("body", "")).strip()
    if not body:
        raise ApiError("Comment cannot be empty")
    author = str(payload.get("author", "")).strip() or db.get_settings().get("user", "You")
    db.add_comment(capa_id, author, body)
    return {"ok": True}


def add_task(capa_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    desc = str(payload.get("description", "")).strip()
    if not desc:
        raise ApiError("Task description is required")
    due = str(payload.get("due_date", "")).strip()
    if due:
        try:
            date.fromisoformat(due)
        except ValueError:
            raise ApiError("Invalid due date (expected YYYY-MM-DD)")
    db.add_task(capa_id, desc, str(payload.get("assignee", "")).strip(), due)
    return {"ok": True}


def toggle_task(task_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    conn = db.connect()
    try:
        row = conn.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ApiError("Task not found", 404)
    db.toggle_task(task_id, bool(payload.get("done")))
    return {"ok": True}


def delete_task(task_id: int) -> dict[str, Any]:
    db.delete_task(task_id)
    return {"ok": True}


def add_document(capa_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ApiError("Document name is required")
    db.add_document(capa_id, name, str(payload.get("path", "")).strip())
    return {"ok": True}


def delete_document(doc_id: int) -> dict[str, Any]:
    db.delete_document(doc_id)
    return {"ok": True}


def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = set(db.DEFAULT_SETTINGS)
    for key, value in payload.items():
        if key in allowed:
            db.set_setting(key, str(value))
    return {"settings": db.get_settings()}


# --------------------------------------------------------------- exports

def register_csv() -> tuple[str, bytes]:
    text = reporting.register_csv_text()
    name = f"CAPA_register_{datetime.now():%Y%m%d}.csv"
    return name, ("\ufeff" + text).encode("utf-8")


def capa_report_txt(capa_id: int) -> tuple[str, str]:
    row = db.get_capa(capa_id)
    if row is None:
        raise ApiError("CAPA not found", 404)
    text = reporting.capa_to_text(capa_id)
    name = f"{row['capa_number'].replace('/', '-')}_report.txt"
    return name, text
