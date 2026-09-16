"""
mongo.py — optional MongoDB Atlas mirror.

If MONGODB_URI is unset or unreachable, every call is a no-op so offline
exams and local demos still work. SQLite remains the source of truth.
"""

from __future__ import annotations

import os
from typing import Any, Optional

_client = None
_db = None
_enabled = False
_last_error: Optional[str] = None


def configure_from_env() -> bool:
    """Load .env if present and connect. Returns True if Atlas is usable."""
    global _client, _db, _enabled, _last_error
    _last_error = None

    try:
        from dotenv import load_dotenv

        # Anchor to repo root
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        load_dotenv(root / ".env")
    except ImportError:
        pass

    uri = os.environ.get("MONGODB_URI", "").strip()
    db_name = os.environ.get("MONGODB_DB", "cerberus").strip() or "cerberus"
    if not uri:
        _enabled = False
        return False

    try:
        from pymongo import MongoClient

        _client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        # Force a round-trip so we know connectivity now.
        _client.admin.command("ping")
        _db = _client[db_name]
        _enabled = True
        return True
    except Exception as exc:  # noqa: BLE001 — soft-fail for demo resilience
        _enabled = False
        _last_error = str(exc)
        _client = None
        _db = None
        return False


def is_enabled() -> bool:
    return _enabled


def last_error() -> Optional[str]:
    return _last_error


def insert_event(doc: dict[str, Any]) -> None:
    if not _enabled or _db is None:
        return
    try:
        _db.events.insert_one(doc)
    except Exception as exc:  # noqa: BLE001
        global _last_error
        _last_error = str(exc)


def insert_snapshot(doc: dict[str, Any]) -> None:
    if not _enabled or _db is None:
        return
    try:
        _db.snapshots.insert_one(doc)
    except Exception as exc:  # noqa: BLE001
        global _last_error
        _last_error = str(exc)


def recent_events(limit: int = 50) -> list[dict[str, Any]]:
    if not _enabled or _db is None:
        return []
    try:
        cur = _db.events.find().sort("ts", -1).limit(limit)
        out = []
        for d in cur:
            d.pop("_id", None)
            out.append(d)
        return out
    except Exception as exc:  # noqa: BLE001
        global _last_error
        _last_error = str(exc)
        return []
