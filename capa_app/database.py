"""SQLite persistence layer for the CAPA Desktop application."""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date, timedelta
from typing import Any, Optional

APP_DIR_NAME = "CAPA"


def data_dir() -> str:
    """Return (creating if needed) the per-user data directory.

    On Windows this resolves to %LOCALAPPDATA%\\CAPA; elsewhere ~/.CAPA.
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~")
    path = os.path.join(base, APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


DB_PATH = os.path.join(data_dir(), "capa.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS capa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capa_number TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,                -- Audit / Complaint / Deviation / Inspection / Nonconformance
    product TEXT DEFAULT '',
    site TEXT DEFAULT '',
    originator TEXT DEFAULT '',
    owner TEXT DEFAULT '',
    priority TEXT DEFAULT 'Medium',      -- Low / Medium / High / Critical
    status TEXT DEFAULT 'Open',          -- Open / In Progress / Verification / Closed / Overdue(computed)
    root_cause_method TEXT DEFAULT '',   -- 5-Why / Fishbone / FMEA / Is-Is Not / 8D
    problem_statement TEXT DEFAULT '',
    root_cause TEXT DEFAULT '',
    containment TEXT DEFAULT '',
    corrective_action TEXT DEFAULT '',
    preventive_action TEXT DEFAULT '',
    effectiveness_check TEXT DEFAULT '',
    opened_on TEXT NOT NULL,             -- ISO date
    target_date TEXT NOT NULL,           -- ISO date
    closed_on TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capa_id INTEGER NOT NULL REFERENCES capa(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    done INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capa_id INTEGER NOT NULL REFERENCES capa(id) ON DELETE CASCADE,
    ts TEXT DEFAULT (datetime('now')),
    kind TEXT NOT NULL,                  -- comment / status / field
    author TEXT DEFAULT 'You',
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capa_id INTEGER NOT NULL REFERENCES capa(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    path TEXT DEFAULT '',
    added_on TEXT DEFAULT (date('now'))
);
"""

DEFAULT_SETTINGS = {
    "company": "Acme Medical Devices Inc.",
    "site": "Plant 1 - Springfield",
    "qms_reference": "QMS-SOP-0420 Corrective and Preventive Action",
    "user": "Quality Manager",
}

CAPA_FIELDS = [
    "title", "source", "product", "site", "originator", "owner", "priority",
    "status", "root_cause_method", "problem_statement", "root_cause",
    "containment", "corrective_action", "preventive_action",
    "effectiveness_check", "opened_on", "target_date", "closed_on",
]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(seed: bool = True) -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        for k, v in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
        if seed and conn.execute("SELECT COUNT(*) c FROM capa").fetchone()["c"] == 0:
            _seed(conn)
        conn.commit()
    finally:
        conn.close()


def get_settings() -> dict[str, str]:
    conn = connect()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------- CRUD

def next_capa_number() -> str:
    year = date.today().year
    conn = connect()
    try:
        n = conn.execute(
            "SELECT COUNT(*) c FROM capa WHERE capa_number LIKE ?",
            (f"CAPA-{year}-%",)).fetchone()["c"]
    finally:
        conn.close()
    return f"CAPA-{year}-{n + 1:03d}"


def create_capa(data: dict[str, Any]) -> int:
    cols = ["capa_number"] + CAPA_FIELDS
    placeholders = ", ".join("?" for _ in cols)
    values = [data.get("capa_number") or next_capa_number()]
    for c in CAPA_FIELDS:
        v = data.get(c)
        if v is None:
            v = date.today().isoformat() if c == "opened_on" else ""
        values.append(v)
    conn = connect()
    try:
        cur = conn.execute(
            f"INSERT INTO capa({', '.join(cols)}) VALUES ({placeholders})", values)
        cid = cur.lastrowid
        conn.execute(
            "INSERT INTO events(capa_id, kind, body) VALUES (?, 'status', ?)",
            (cid, f"CAPA created (status: {data.get('status', 'Open')})"))
        conn.commit()
        return cid
    finally:
        conn.close()


def update_capa(capa_id: int, data: dict[str, Any]) -> None:
    sets, values = [], []
    for f in CAPA_FIELDS:
        if f in data:
            sets.append(f"{f} = ?")
            values.append(data[f])
    if not sets:
        return
    values.append(capa_id)
    conn = connect()
    try:
        old = conn.execute("SELECT status FROM capa WHERE id=?", (capa_id,)).fetchone()
        conn.execute(
            f"UPDATE capa SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?", values)
        if old and "status" in data and data["status"] != old["status"]:
            conn.execute(
                "INSERT INTO events(capa_id, kind, body) VALUES (?, 'status', ?)",
                (capa_id, f"Status changed: {old['status']} → {data['status']}"))
        conn.commit()
    finally:
        conn.close()


def delete_capa(capa_id: int) -> None:
    conn = connect()
    try:
        conn.execute("DELETE FROM capa WHERE id = ?", (capa_id,))
        conn.commit()
    finally:
        conn.close()


def get_capa(capa_id: int) -> Optional[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute("SELECT * FROM capa WHERE id = ?", (capa_id,)).fetchone()
    finally:
        conn.close()


def list_capas(search: str = "", status: str = "", priority: str = "",
               order_by: str = "target_date ASC") -> list[sqlite3.Row]:
    sql = "SELECT * FROM capa WHERE 1=1"
    args: list[Any] = []
    if search:
        like = f"%{search}%"
        sql += (" AND (capa_number LIKE ? OR title LIKE ? OR product LIKE ?"
                " OR owner LIKE ? OR problem_statement LIKE ?)")
        args += [like] * 5
    if status:
        statuses = [s.strip() for s in status.split("|") if s.strip()]
        sql += f" AND status IN ({','.join('?' for _ in statuses)})"
        args += statuses
    if priority:
        prios = [p.strip() for p in priority.split("|") if p.strip()]
        sql += f" AND priority IN ({','.join('?' for _ in prios)})"
        args += prios
    allowed = {"target_date ASC", "target_date DESC", "opened_on DESC",
               "capa_number ASC", "priority DESC", "status ASC"}
    if order_by in allowed:
        sql += f" ORDER BY {order_by}"
    conn = connect()
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


# ------------------------------------------------------------------ helpers

def is_overdue(row: sqlite3.Row) -> bool:
    if row["status"] == "Closed":
        return False
    try:
        return date.fromisoformat(row["target_date"]) < date.today()
    except (ValueError, TypeError):
        return False


def effective_status(row: sqlite3.Row) -> str:
    return "Overdue" if is_overdue(row) else row["status"]


def days_remaining(row: sqlite3.Row) -> Optional[int]:
    try:
        return (date.fromisoformat(row["target_date"]) - date.today()).days
    except (ValueError, TypeError):
        return None


def metrics() -> dict[str, int]:
    rows = list_capas()
    m = {"total": len(rows), "open": 0, "in_progress": 0, "verification": 0,
         "closed": 0, "overdue": 0, "closed_this_month": 0}
    month = date.today().strftime("%Y-%m")
    for r in rows:
        st = effective_status(r)
        if st == "Overdue":
            m["overdue"] += 1
        elif st == "Open":
            m["open"] += 1
        elif st == "In Progress":
            m["in_progress"] += 1
        elif st == "Verification":
            m["verification"] += 1
        elif st == "Closed":
            m["closed"] += 1
            if (r["closed_on"] or "").startswith(month):
                m["closed_this_month"] += 1
    return m


# ------------------------------------------------------------------- tasks

def add_task(capa_id: int, description: str, assignee: str, due_date: str) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO tasks(capa_id, description, assignee, due_date) "
            "VALUES (?, ?, ?, ?)", (capa_id, description, assignee, due_date))
        conn.commit()
    finally:
        conn.close()


def toggle_task(task_id: int, done: bool) -> None:
    conn = connect()
    try:
        conn.execute("UPDATE tasks SET done = ? WHERE id = ?", (int(done), task_id))
        conn.commit()
    finally:
        conn.close()


def delete_task(task_id: int) -> None:
    conn = connect()
    try:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()


def list_tasks(capa_id: int) -> list[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM tasks WHERE capa_id = ? ORDER BY done, due_date",
            (capa_id,)).fetchall()
    finally:
        conn.close()


# ------------------------------------------------------------------ events

def add_comment(capa_id: int, author: str, body: str) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO events(capa_id, kind, author, body) VALUES (?, 'comment', ?, ?)",
            (capa_id, author, body))
        conn.commit()
    finally:
        conn.close()


def list_events(capa_id: int) -> list[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM events WHERE capa_id = ? ORDER BY ts DESC, id DESC",
            (capa_id,)).fetchall()
    finally:
        conn.close()


# --------------------------------------------------------------- documents

def add_document(capa_id: int, name: str, path: str = "") -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO documents(capa_id, name, path) VALUES (?, ?, ?)",
            (capa_id, name, path))
        conn.commit()
    finally:
        conn.close()


def list_documents(capa_id: int) -> list[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM documents WHERE capa_id = ? ORDER BY id", (capa_id,)).fetchall()
    finally:
        conn.close()


def delete_document(doc_id: int) -> None:
    conn = connect()
    try:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
    finally:
        conn.close()


# -------------------------------------------------------------------- seed

def _seed(conn: sqlite3.Connection) -> None:
    today = date.today()

    def d(days: int) -> str:
        return (today + timedelta(days=days)).isoformat()

    samples = [
        dict(capa_number=f"CAPA-{today.year - 1}-014",
             title="Tablet weight variation outside spec on Line 3",
             source="Deviation", product="Metformin 500 mg Tablets",
             site="Plant 1 - Springfield", originator="J. Alvarez", owner="M. Chen",
             priority="High", status="In Progress", root_cause_method="5-Why",
             problem_statement="Between batches 24-091 and 24-097, tablet weight RSD exceeded "
                               "the 3.0% acceptance criterion on Line 3 during in-process checks.",
             root_cause="Punch tip wear on station 14 led to inconsistent fill depth; "
                        "wear was not detected because the punch inspection interval was too long.",
             containment="Quarantine affected batches; 100% weight check of retained samples.",
             corrective_action="Replace all Station 14 punches; recalibrate force feeder.",
             preventive_action="Reduce punch inspection interval from quarterly to monthly; "
                               "add RSD trend alert to MES dashboard.",
             opened_on=d(-64), target_date=d(9)),
        dict(capa_number=f"CAPA-{today.year}-001",
             title="Patient complaint - blister card misprint",
             source="Complaint", product="Lisinopril 10 mg", site="Plant 1 - Springfield",
             originator="Customer Service", owner="S. Patel", priority="Critical",
             status="Verification", root_cause_method="Fishbone",
             problem_statement="Two complaints received reporting cartons printed with the "
                               "wrong strength statement (20 mg instead of 10 mg).",
             root_cause="Manual plate change at the packaging line used an archived artwork "
                        "version; no barcode verification step existed.",
             containment="Recall assessment initiated; lot 25-011 quarantined and sampled.",
             corrective_action="Install inline OCR/artwork verification camera on Line 1.",
             preventive_action="Artwork retrieval moved to controlled digital workflow with "
                               "two-person release.",
             effectiveness_check="Verify zero misprint events over 3 consecutive months.",
             opened_on=d(-31), target_date=d(4)),
        dict(capa_number=f"CAPA-" + str(today.year) + "-002",
             title="HVLC room differential pressure excursions",
             source="Inspection", product="-", site="Plant 2 - Northgate",
             originator="Facilities", owner="R. Kowalski", priority="Medium",
             status="Open", root_cause_method="Is-Is Not",
             problem_statement="Three BMS alarms for HVLC room 214 differential pressure "
                               "below 10 Pa during night shift.",
             opened_on=d(-6), target_date=d(24)),
        dict(capa_number=f"CAPA-{today.year}-003",
             title="Data integrity finding: shared login on GC workstation",
             source="Audit", product="-", site="Plant 1 - Springfield",
             originator="Internal Audit", owner="T. Nguyen", priority="High",
             status="Closed", root_cause_method="8D",
             problem_statement="Audit found two analysts sharing a single instrument login "
                               "on GC workstation W-118, preventing attributable records.",
             root_cause="Instrument software provisioned before individual AD accounts existed; "
                        "no periodic access review.",
             corrective_action="Provisioned unique accounts; disabled shared login.",
             preventive_action="Added instrument logins to quarterly access review checklist.",
             effectiveness_check="Access review Q1 completed with no findings.",
             opened_on=d(-120), target_date=d(-40), closed_on=d(-38)),
        dict(capa_number=f"CAPA-{today.year}-004",
             title="Capsule weight loss above limit after bottle packing",
             source="Nonconformance", product="Omeprazole 20 mg DR Capsules",
             site="Plant 2 - Northgate", originator="Production", owner="M. Chen",
             priority="Medium", status="In Progress", root_cause_method="FMEA",
             problem_statement="Finished product moisture pickup observed 30 days after "
                               "packaging into HDPE bottles with induction seal liner Lot S-88.",
             opened_on=d(-18), target_date=d(-2)),
        dict(capa_number=f"CAPA-{today.year}-005",
             title="Cleaning validation swab recovery below acceptance",
             source="Deviation", product="Shared equipment - Mixer M-04",
             site="Plant 1 - Springfield", originator="Validation", owner="A. Rossi",
             priority="Low", status="Open", root_cause_method="5-Why",
             problem_statement="Swab recovery at the agitator shaft seal ranged 42-58% versus "
                               "the >=70% acceptance criterion in CV protocol CV-021.",
             opened_on=d(-2), target_date=d(45)),
    ]

    for s in samples:
        cols = [c for c in s if c != "capa_number"] + ["capa_number"]
        vals = [s[c] for c in cols]
        conn.execute(
            f"INSERT INTO capa({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            vals)

    rows = conn.execute("SELECT id, capa_number FROM capa ORDER BY id").fetchall()
    ids = [r["id"] for r in rows]

    tasks = [
        (ids[0], "Replace Station 14 punch set", "Maintenance - D. Kim", d(3), 0),
        (ids[0], "Update SOP-MFG-102 inspection interval", "M. Chen", d(12), 0),
        (ids[0], "Retrain line operators on RSD trending", "Training Dept", d(20), 0),
        (ids[1], "Complete recall reconciliation report", "S. Patel", d(2), 0),
        (ids[1], "IQ/OQ of artwork verification camera", "Engineering", d(-1), 1),
        (ids[3], "Archive audit response memo", "T. Nguyen", d(-45), 1),
        (ids[4], "Evaluate liner Lot S-88 supplier COAs", "Procurement QA", d(-5), 0),
    ]
    for t in tasks:
        conn.execute(
            "INSERT INTO tasks(capa_id, description, assignee, due_date, done) "
            "VALUES (?, ?, ?, ?, ?)", t)

    events = [
        (ids[0], "Deviation Review Board approved CAPA scope.", "QA Board"),
        (ids[1], "Health authority notification submitted within 24h.", "Regulatory"),
        (ids[1], "Effectiveness check plan agreed with QA head.", "S. Patel"),
        (ids[4], "Supplier notified; replacement liner material under evaluation.", "Procurement QA"),
    ]
    for e in events:
        conn.execute(
            "INSERT INTO events(capa_id, kind, author, body) VALUES (?, 'comment', ?, ?)", e)

    docs = [
        (ids[0], "IPC weight data - Line 3.xlsx", ""),
        (ids[1], "Complaint forms C-2541, C-2547.pdf", ""),
        (ids[1], "Artwork verification FAT report.pdf", ""),
        (ids[3], "IA Report 2025-07 signed.pdf", ""),
    ]
    for doc in docs:
        conn.execute(
            "INSERT INTO documents(capa_id, name) VALUES (?, ?)", doc[:2])
