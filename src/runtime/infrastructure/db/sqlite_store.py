import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from runtime.domain.models import RunStatus


class StateStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY,
                  skill_name TEXT NOT NULL,
                  status TEXT NOT NULL,
                  current_step INTEGER NOT NULL DEFAULT 0,
                  context_json TEXT NOT NULL DEFAULT '{}',
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS waits (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  wait_key TEXT NOT NULL,
                  match_json TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  expires_at TEXT,
                  FOREIGN KEY(run_id) REFERENCES runs(id)
                );

                CREATE TABLE IF NOT EXISTS events (
                  id TEXT PRIMARY KEY,
                  run_id TEXT,
                  type TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_runs_status_updated_at ON runs(status, updated_at);
                CREATE INDEX IF NOT EXISTS idx_waits_wait_key_status ON waits(wait_key, status);
                CREATE INDEX IF NOT EXISTS idx_events_run_created_at ON events(run_id, created_at);
                """
            )
            self._ensure_column(conn, "waits", "step_id TEXT")
            self._ensure_column(conn, "waits", "resolved_at TEXT")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, definition: str) -> None:
        column = definition.split()[0]
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in rows}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

    def create_run(self, skill_name: str, context: dict[str, Any]) -> str:
        run_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (id, skill_name, status, current_step, context_json)
                VALUES (?, ?, ?, 0, ?)
                """,
                (run_id, skill_name, RunStatus.CREATED.value, json.dumps(context)),
            )
        return run_id

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        current_step: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        updates: list[str] = []
        params: list[Any] = []

        if status is not None:
            updates.append("status = ?")
            params.append(status.value)
        if current_step is not None:
            updates.append("current_step = ?")
            params.append(current_step)
        if context is not None:
            updates.append("context_json = ?")
            params.append(json.dumps(context))

        if not updates:
            return

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(run_id)

        query = f"UPDATE runs SET {', '.join(updates)} WHERE id = ?"
        with self._connect() as conn:
            conn.execute(query, params)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, skill_name, status, current_step, context_json, created_at, updated_at
                FROM runs WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "skill_name": row["skill_name"],
            "status": row["status"],
            "current_step": row["current_step"],
            "context": json.loads(row["context_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def append_event(self, event_type: str, payload: dict[str, Any], run_id: str | None = None) -> str:
        event_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO events (id, run_id, type, payload_json) VALUES (?, ?, ?, ?)",
                (event_id, run_id, event_type, json.dumps(payload)),
            )
        return event_id

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, type, payload_json, created_at
                FROM events WHERE run_id = ?
                ORDER BY rowid ASC
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "type": row["type"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def create_wait(
        self,
        run_id: str,
        wait_key: str,
        match: dict[str, Any],
        *,
        step_id: str | None = None,
        expires_at: str | None = None,
    ) -> str:
        wait_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO waits (id, run_id, step_id, wait_key, match_json, status, expires_at)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?)
                """,
                (wait_id, run_id, step_id, wait_key, json.dumps(match), expires_at),
            )
        return wait_id

    def resolve_wait(self, wait_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE waits
                SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (wait_id,),
            )

    def find_matching_waits(self, wait_key: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, run_id, step_id, wait_key, match_json, status, created_at, resolved_at, expires_at
                FROM waits
                WHERE wait_key = ? AND status = 'ACTIVE'
                ORDER BY created_at ASC
                """,
                (wait_key,),
            ).fetchall()

        matches: list[dict[str, Any]] = []
        for row in rows:
            match = json.loads(row["match_json"])
            if self._payload_matches(match, payload):
                matches.append(
                    {
                        "id": row["id"],
                        "run_id": row["run_id"],
                        "step_id": row["step_id"],
                        "wait_key": row["wait_key"],
                        "match": match,
                        "status": row["status"],
                        "created_at": row["created_at"],
                        "resolved_at": row["resolved_at"],
                        "expires_at": row["expires_at"],
                    }
                )
        return matches

    def _payload_matches(self, expected: dict[str, Any], payload: dict[str, Any]) -> bool:
        for key, value in expected.items():
            if payload.get(key) != value:
                return False
        return True
