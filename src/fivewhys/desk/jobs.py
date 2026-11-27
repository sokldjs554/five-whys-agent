"""Persistent, single-host incident queue. SQLite serializes claims across workers."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

MAX_RUNTIME = 180


class JobStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS desk_jobs (
                id TEXT PRIMARY KEY, question TEXT NOT NULL, engine TEXT NOT NULL,
                status TEXT NOT NULL, created_at REAL NOT NULL, started_at REAL,
                finished_at REAL, expires_at REAL, error TEXT, result TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS desk_messages (
                job_id TEXT NOT NULL, citation_id TEXT NOT NULL, body TEXT NOT NULL,
                PRIMARY KEY(job_id, citation_id))""")
            conn.execute("CREATE INDEX IF NOT EXISTS desk_queue ON desk_jobs(status, created_at)")

    def enqueue(self, question, engine):
        job_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            count = conn.execute(
                "SELECT count(*) FROM desk_jobs WHERE status IN ('queued','running')"
            ).fetchone()[0]
            if count >= 32:
                raise OverflowError("queue full")
            conn.execute("INSERT INTO desk_jobs(id,question,engine,status,created_at) "
                         "VALUES (?,?,?,'queued',?)", (job_id, question, engine, time.time()))
        return job_id

    def claim(self):
        now = time.time()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("""UPDATE desk_jobs SET status='failed',error='WorkerExpired',finished_at=?
                            WHERE status='running' AND expires_at<=?""", (now, now))
            row = conn.execute("SELECT id,question,engine FROM desk_jobs WHERE status='queued' "
                               "ORDER BY created_at,id LIMIT 1").fetchone()
            if row:
                conn.execute("UPDATE desk_jobs SET status='running', started_at=?,expires_at=? "
                             "WHERE id=?", (now, now + MAX_RUNTIME + 15, row["id"]))
                return dict(row)
        return None

    def finish(self, job_id, result=None, error=None):
        status = "failed" if error else ("completed" if result["status"] == "answered" else "withheld")
        with self.connect() as conn:
            conn.execute("""UPDATE desk_jobs SET status=?,result=?,error=?,finished_at=?
                            WHERE id=? AND status='running'""",
                         (status, json.dumps(result, ensure_ascii=False) if result else None,
                          error, time.time(), job_id))

    def read(self, job_id):
        with self.connect() as conn:
            row = conn.execute("SELECT id,question,engine,status,created_at,started_at,finished_at,error "
                               "FROM desk_jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def result(self, job_id):
        with self.connect() as conn:
            row = conn.execute("SELECT result FROM desk_jobs WHERE id=?", (job_id,)).fetchone()
        return json.loads(row["result"]) if row and row["result"] else None

    def quote(self, job_id, citation):
        message = {"question": f"{citation['id']} 인용의 출처와 원문을 보여 줘.",
                   "reply": citation, "model_calls": 0}
        with self.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO desk_messages VALUES (?,?,?)",
                         (job_id, citation["id"], json.dumps(message, ensure_ascii=False)))
        return message

    def messages(self, job_id):
        with self.connect() as conn:
            rows = conn.execute("SELECT body FROM desk_messages WHERE job_id=? ORDER BY rowid", (job_id,))
            return [json.loads(row["body"]) for row in rows]
