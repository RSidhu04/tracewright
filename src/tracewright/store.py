import json
import sqlite3
from contextlib import closing
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)")

    def save(self, run):
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("INSERT INTO runs VALUES (?, ?, ?)",
                         (run["id"], run["created_at"], json.dumps(run, allow_nan=False)))

    def get(self, run_id):
        with closing(sqlite3.connect(self.path)) as conn:
            row = conn.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return json.loads(row[0])

    def list(self, limit=100):
        with closing(sqlite3.connect(self.path)) as conn:
            rows = conn.execute("SELECT id, created_at FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": row[0], "created_at": row[1]} for row in rows]
