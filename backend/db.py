"""
db.py — SQLite schema and helpers for Cerberus (local source of truth).

WHY PATH FROM __file__
----------------------
A past bug opened different .db files depending on the process cwd.
Every component must resolve the DB relative to this module so collector,
CLI, API, and control loop all share one database.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

# Always anchor to this file — never cwd.
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = _DATA_DIR / "cerberus.db"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None) -> sqlite3.Connection:
    own = conn is None
    conn = conn or get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            total_pkts INTEGER NOT NULL DEFAULT 0,
            dropped INTEGER NOT NULL DEFAULT 0,
            passed INTEGER NOT NULL DEFAULT 0,
            threshold INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS ip_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            src_ip TEXT NOT NULL,
            count INTEGER NOT NULL,
            action TEXT NOT NULL DEFAULT 'pass'
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            type TEXT NOT NULL,
            src_ip TEXT,
            detail TEXT
        );

        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
        CREATE INDEX IF NOT EXISTS idx_ip_stats_ts ON ip_stats(ts);
        """
    )
    conn.commit()
    if own:
        return conn
    return conn


def set_config(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO config(key, value, updated_at) VALUES(?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """,
        (key, value, time.time()),
    )
    conn.commit()


def get_config(conn: sqlite3.Connection, key: str, default: Optional[str] = None) -> Optional[str]:
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def insert_snapshot(
    conn: sqlite3.Connection,
    total_pkts: int,
    dropped: int,
    passed: int,
    threshold: int,
    ts: Optional[float] = None,
) -> None:
    conn.execute(
        "INSERT INTO snapshots(ts, total_pkts, dropped, passed, threshold) VALUES(?,?,?,?,?)",
        (ts or time.time(), total_pkts, dropped, passed, threshold),
    )
    conn.commit()


def insert_ip_stats(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    ts: Optional[float] = None,
) -> None:
    now = ts or time.time()
    conn.executemany(
        "INSERT INTO ip_stats(ts, src_ip, count, action) VALUES(?,?,?,?)",
        [(now, r["ip"], r["count"], r.get("action", "pass")) for r in rows],
    )
    conn.commit()


def insert_event(
    conn: sqlite3.Connection,
    event_type: str,
    src_ip: Optional[str] = None,
    detail: Optional[str] = None,
    ts: Optional[float] = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO events(ts, type, src_ip, detail) VALUES(?,?,?,?)",
        (ts or time.time(), event_type, src_ip, detail),
    )
    conn.commit()
    return int(cur.lastrowid)


def recent_snapshots(conn: sqlite3.Connection, limit: int = 60) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM snapshots ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def recent_events(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def latest_ip_stats(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Most recent collector batch's top IPs (approx via latest ts)."""
    row = conn.execute("SELECT MAX(ts) AS m FROM ip_stats").fetchone()
    if not row or row["m"] is None:
        return []
    rows = conn.execute(
        """
        SELECT src_ip, count, action FROM ip_stats
        WHERE ts = ? ORDER BY count DESC LIMIT ?
        """,
        (row["m"], limit),
    ).fetchall()
    return [dict(r) for r in rows]
