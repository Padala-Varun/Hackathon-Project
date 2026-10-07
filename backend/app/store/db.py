"""Tiny SQLite document store: records, MOPs, logs, mock tickets and notifications as JSON rows."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

TABLES = ("records", "mops", "logs", "tickets")


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            for t in TABLES:
                self._conn.execute(f"CREATE TABLE IF NOT EXISTS {t} (id TEXT PRIMARY KEY, source TEXT, data TEXT)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL, data TEXT)"
            )

    def upsert(self, table: str, id: str, data: dict[str, Any], source: str = "") -> None:
        with self._lock, self._conn:
            self._conn.execute(
                f"INSERT OR REPLACE INTO {table} (id, source, data) VALUES (?, ?, ?)", (id, source, json.dumps(data))
            )

    def upsert_many(self, table: str, rows: list[tuple[str, dict[str, Any], str]]) -> None:
        with self._lock, self._conn:
            self._conn.executemany(
                f"INSERT OR REPLACE INTO {table} (id, source, data) VALUES (?, ?, ?)",
                [(i, s, json.dumps(d)) for i, d, s in rows],
            )

    def get(self, table: str, id: str) -> dict[str, Any] | None:
        row = self._conn.execute(f"SELECT data FROM {table} WHERE id = ?", (id,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self, table: str) -> list[dict[str, Any]]:
        return [json.loads(r[0]) for r in self._conn.execute(f"SELECT data FROM {table} ORDER BY id")]

    def clear(self, table: str, source: str | None = None) -> None:
        with self._lock, self._conn:
            if source is None:
                self._conn.execute(f"DELETE FROM {table}")
            else:
                self._conn.execute(f"DELETE FROM {table} WHERE source = ?", (source,))

    def count(self, table: str) -> int:
        return self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def add_notification(self, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO notifications (created, data) VALUES (?, ?)", (time.time(), json.dumps(data))
            )
        return {"id": cur.lastrowid, **data}

    def notifications(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, created, data FROM notifications ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"id": i, "created": c, **json.loads(d)} for i, c, d in rows]
