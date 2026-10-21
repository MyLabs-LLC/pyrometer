"""SQLite sample store (standard library only)."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pyrometer.core.sample import Sample

_SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    ts    REAL NOT NULL,
    name  TEXT NOT NULL,
    value REAL NOT NULL,
    tags  TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS samples_name_ts ON samples (name, ts);
"""


class SQLiteStorage:
    """Stores samples in one ``samples`` table; tags are a JSON object.

    Writes from one sampler tick go in a single transaction. The connection
    is shared across threads behind a lock so a background sampler and a
    reader in the main thread can use the same store.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            if self.path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)

    def write(self, samples: Sequence[Sample]) -> None:
        if not samples:
            return
        rows = [
            (s.timestamp, s.name, s.value, json.dumps(dict(s.tags), sort_keys=True))
            for s in samples
        ]
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT INTO samples (ts, name, value, tags) VALUES (?, ?, ?, ?)", rows
            )

    def query(
        self,
        name: str | None = None,
        since: float | None = None,
        until: float | None = None,
        tags: Mapping[str, str] | None = None,
    ) -> list[Sample]:
        sql = "SELECT ts, name, value, tags FROM samples WHERE 1=1"
        params: list[Any] = []
        if name is not None:
            sql += " AND name = ?"
            params.append(name)
        if since is not None:
            sql += " AND ts >= ?"
            params.append(since)
        if until is not None:
            sql += " AND ts <= ?"
            params.append(until)
        for key, value in (tags or {}).items():
            sql += " AND json_extract(tags, ?) = ?"
            params += [f'$."{key}"', value]
        sql += " ORDER BY ts, rowid"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [Sample(ts, n, v, json.loads(t)) for ts, n, v, t in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
