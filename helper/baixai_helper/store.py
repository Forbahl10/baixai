"""Persistência em SQLite: trabalhos, logs e preferências. Thread-safe (lock + uma conexão)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from . import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, created_at REAL NOT NULL, updated_at REAL NOT NULL,
  url TEXT NOT NULL, platform TEXT, engine TEXT NOT NULL, mode TEXT NOT NULL, options TEXT NOT NULL DEFAULT '{}',
  meta TEXT NOT NULL DEFAULT '{}', dedupe_key TEXT NOT NULL, state TEXT NOT NULL, stage TEXT,
  progress REAL, speed REAL, eta REAL, detail TEXT, files TEXT NOT NULL DEFAULT '[]', notes TEXT NOT NULL DEFAULT '[]',
  error_code TEXT, error_message TEXT, error_detail TEXT, attempts INTEGER NOT NULL DEFAULT 0, dest_dir TEXT
);
CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS jobs_dedupe ON jobs(dedupe_key);
CREATE TABLE IF NOT EXISTS job_logs (job_id TEXT NOT NULL, ts REAL NOT NULL, line TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS job_logs_job ON job_logs(job_id);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""
JSON_COLS = ("options", "meta", "files", "notes")
ACTIVE = ("waiting", "analyzing", "downloading", "converting")
MAX_LOG_LINES = 300


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or (paths.data_dir() / "baixai.db")
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # --- kv
    def get_kv(self, key: str) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
        return row["v"] if row else None

    def set_kv(self, key: str, value: str) -> None:
        with self._lock:
            self._db.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, value))

    # --- jobs
    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        d = dict(row)
        for c in JSON_COLS:
            d[c] = json.loads(d[c])
        return d

    def insert(self, job: dict) -> None:
        now = time.time()
        cols = {**job, "created_at": now, "updated_at": now}
        for c in JSON_COLS:
            cols[c] = json.dumps(cols.get(c, {} if c in ("options", "meta") else []), ensure_ascii=False)
        keys = ",".join(cols)
        with self._lock:
            self._db.execute(f"INSERT INTO jobs({keys}) VALUES({','.join('?' * len(cols))})", list(cols.values()))

    def update(self, job_id: str, **fields) -> None:
        fields["updated_at"] = time.time()
        for c in JSON_COLS:
            if c in fields:
                fields[c] = json.dumps(fields[c], ensure_ascii=False)
        sets = ",".join(f"{k}=?" for k in fields)
        with self._lock:
            self._db.execute(f"UPDATE jobs SET {sets} WHERE id=?", [*fields.values(), job_id])

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            return self._row(self._db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def list(self, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row(r) for r in rows]

    def by_state(self, states: tuple[str, ...]) -> list[dict]:
        q = ",".join("?" * len(states))
        with self._lock:
            rows = self._db.execute(f"SELECT * FROM jobs WHERE state IN ({q}) ORDER BY created_at ASC", states).fetchall()
        return [self._row(r) for r in rows]

    def find_by_dedupe(self, key: str, states: tuple[str, ...]) -> dict | None:
        q = ",".join("?" * len(states))
        with self._lock:
            row = self._db.execute(f"SELECT * FROM jobs WHERE dedupe_key=? AND state IN ({q}) ORDER BY created_at DESC LIMIT 1", (key, *states)).fetchone()
        return self._row(row)

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
            self._db.execute("DELETE FROM job_logs WHERE job_id=?", (job_id,))

    def delete_finished(self) -> list[str]:
        with self._lock:
            ids = [r["id"] for r in self._db.execute("SELECT id FROM jobs WHERE state IN ('done','failed','cancelled')")]
            for i in ids:
                self.delete(i)
        return ids

    # --- logs
    def add_log(self, job_id: str, line: str) -> None:
        with self._lock:
            self._db.execute("INSERT INTO job_logs(job_id, ts, line) VALUES(?,?,?)", (job_id, time.time(), line))
            self._db.execute(
                "DELETE FROM job_logs WHERE job_id=? AND rowid NOT IN (SELECT rowid FROM job_logs WHERE job_id=? ORDER BY rowid DESC LIMIT ?)",
                (job_id, job_id, MAX_LOG_LINES),
            )

    def logs(self, job_id: str) -> list[str]:
        with self._lock:
            rows = self._db.execute("SELECT line FROM job_logs WHERE job_id=? ORDER BY rowid", (job_id,)).fetchall()
        return [r["line"] for r in rows]
