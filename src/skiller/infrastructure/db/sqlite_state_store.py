import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunStatus
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType
from skiller.domain.wait.wait_type import WaitType
from skiller.infrastructure.db.sqlite_agent_context_store import ensure_agent_context_schema
from skiller.infrastructure.db.sqlite_external_event_store import SqliteExternalEventStore
from skiller.infrastructure.db.sqlite_repository import SqliteRepository
from skiller.infrastructure.db.sqlite_run_mapper import build_run_from_row
from skiller.infrastructure.db.sqlite_wait_store import SqliteWaitStore


class SqliteStateStore(SqliteRepository):
    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)
        self.wait_store = SqliteWaitStore(db_path)
        self.external_event_store = SqliteExternalEventStore(db_path)

    def init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY,
                  skill_source TEXT NOT NULL,
                  skill_ref TEXT NOT NULL,
                  skill_snapshot_json TEXT NOT NULL,
                  status TEXT NOT NULL,
                  current TEXT,
                  inputs_json TEXT NOT NULL DEFAULT '{}',
                  step_executions_json TEXT NOT NULL DEFAULT '{}',
                  steering_messages_json TEXT NOT NULL DEFAULT '[]',
                  cancel_reason TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS events (
                  id TEXT PRIMARY KEY,
                  run_id TEXT,
                  type TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS external_receipts (
                  dedup_key TEXT PRIMARY KEY,
                  source_type TEXT NOT NULL,
                  source_name TEXT NOT NULL,
                  match_type TEXT NOT NULL,
                  match_key TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_runs_status_updated_at ON runs(status, updated_at);
                CREATE INDEX IF NOT EXISTS idx_events_run_created_at
                  ON events(run_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_external_receipts_source_match_created_at
                  ON external_receipts(source_type, source_name, match_type, match_key, created_at);
                """
            )
            self._ensure_waits_table(conn)
            self._ensure_external_events_table(conn)
            ensure_agent_context_schema(conn)
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_waits_run_step_type_status
                  ON waits(run_id, step_id, wait_type, status)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_waits_source_match_type_status
                  ON waits(source_type, source_name, match_type, match_key, wait_type, status)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_external_events_source_run_step_created_at
                  ON external_events(source_type, run_id, step_id, status, created_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_external_events_source_match_created_at
                  ON external_events(
                    source_type,
                    source_name,
                    match_type,
                    match_key,
                    status,
                    created_at
                  )
                """
            )
            self._ensure_runs_current_column(conn)
            self._ensure_runs_step_executions_column(conn)
            self._ensure_runs_steering_messages_column(conn)
            self._drop_runs_current_step_column(conn)

    def create_run(
        self,
        skill_source: str,
        skill_ref: str,
        skill_snapshot: dict[str, object],
        context: RunContext,
        *,
        run_id: str,
    ) -> str:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO runs (
                      id,
                      skill_source,
                      skill_ref,
                      skill_snapshot_json,
                      status,
                      current,
                      inputs_json,
                      step_executions_json,
                      steering_messages_json
                    )
                    VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        run_id,
                        skill_source,
                        skill_ref,
                        json.dumps(skill_snapshot),
                        RunStatus.CREATED.value,
                        json.dumps(context.inputs),
                        json.dumps(context.to_dict()["step_executions"]),
                        json.dumps(context.steering_messages),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Run '{run_id}' already exists") from exc
        return run_id

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        current: str | None = None,
        context: RunContext | None = None,
    ) -> None:
        terminal_statuses = (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED)
        updates: list[str] = []
        params: list[Any] = []

        if status is not None:
            updates.append("status = ?")
            params.append(status.value)
        if current is not None:
            updates.append("current = ?")
            params.append(current)
        if context is not None:
            updates.append("step_executions_json = ?")
            params.append(json.dumps(context.to_dict()["step_executions"]))
            updates.append("steering_messages_json = ?")
            params.append(json.dumps(context.steering_messages))
            updates.append("cancel_reason = ?")
            params.append(context.cancel_reason)
        if status in terminal_statuses:
            updates.append("finished_at = CURRENT_TIMESTAMP")

        if not updates:
            return

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(run_id)

        query = f"UPDATE runs SET {', '.join(updates)} WHERE id = ?"
        with self._connect() as conn:
            conn.execute(query, params)
            if status in terminal_statuses:
                conn.execute(
                    """
                    UPDATE waits
                    SET status = 'EXPIRED', resolved_at = CURRENT_TIMESTAMP
                    WHERE run_id = ? AND status = 'ACTIVE'
                    """,
                    (run_id,),
                )

    def get_run(self, run_id: str) -> Run | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                  id,
                  skill_source,
                  skill_ref,
                  skill_snapshot_json,
                  status,
                  current,
                  inputs_json,
                  step_executions_json,
                  steering_messages_json,
                  cancel_reason,
                  created_at,
                  updated_at
                FROM runs WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return build_run_from_row(row)

    def delete_run(self, run_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                return False

            if self._table_exists(conn, "execution_outputs"):
                conn.execute("DELETE FROM execution_outputs WHERE run_id = ?", (run_id,))
            if self._table_exists(conn, "agent_context_entries"):
                conn.execute("DELETE FROM agent_context_entries WHERE run_id = ?", (run_id,))
            conn.execute(
                """
                DELETE FROM external_receipts
                WHERE dedup_key IN (
                  SELECT dedup_key
                  FROM external_events
                  WHERE (run_id = ? OR consumed_by_run_id = ?)
                    AND dedup_key IS NOT NULL
                )
                """,
                (run_id, run_id),
            )
            conn.execute(
                """
                DELETE FROM external_events
                WHERE run_id = ? OR consumed_by_run_id = ?
                """,
                (run_id, run_id),
            )
            conn.execute("DELETE FROM waits WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM events WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        return True

    def _ensure_runs_current_column(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(runs)").fetchall()
        column_names = {str(row["name"]) for row in rows}
        if "current" in column_names:
            return
        conn.execute("ALTER TABLE runs ADD COLUMN current TEXT")

    def _ensure_runs_step_executions_column(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(runs)").fetchall()
        column_names = {str(row["name"]) for row in rows}
        if "step_executions_json" in column_names:
            return
        conn.execute("ALTER TABLE runs ADD COLUMN step_executions_json TEXT NOT NULL DEFAULT '{}'")

    def _ensure_runs_steering_messages_column(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(runs)").fetchall()
        column_names = {str(row["name"]) for row in rows}
        if "steering_messages_json" in column_names:
            return
        conn.execute(
            "ALTER TABLE runs ADD COLUMN steering_messages_json TEXT NOT NULL DEFAULT '[]'"
        )

    def _drop_runs_current_step_column(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(runs)").fetchall()
        column_names = {str(row["name"]) for row in rows}
        if "current_step" not in column_names:
            return
        conn.execute("ALTER TABLE runs DROP COLUMN current_step")

    def _ensure_waits_table(self, conn: sqlite3.Connection) -> None:
        if not self._table_exists(conn, "waits"):
            conn.execute(
                """
                CREATE TABLE waits (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  step_id TEXT NOT NULL,
                  wait_type TEXT NOT NULL,
                  source_type TEXT NOT NULL,
                  source_name TEXT NOT NULL,
                  match_type TEXT NOT NULL,
                  match_key TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  expires_at TEXT,
                  resolved_at TEXT,
                  FOREIGN KEY(run_id) REFERENCES runs(id)
                )
                """
            )

    def _ensure_external_events_table(self, conn: sqlite3.Connection) -> None:
        if not self._table_exists(conn, "external_events"):
            conn.execute(
                """
                CREATE TABLE external_events (
                  id TEXT PRIMARY KEY,
                  source_type TEXT NOT NULL,
                  source_name TEXT NOT NULL,
                  match_type TEXT NOT NULL,
                  match_key TEXT NOT NULL,
                  run_id TEXT,
                  step_id TEXT,
                  external_id TEXT,
                  dedup_key TEXT,
                  status TEXT NOT NULL,
                  consumed_by_run_id TEXT,
                  consumed_at TEXT,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(run_id) REFERENCES runs(id),
                  FOREIGN KEY(consumed_by_run_id) REFERENCES runs(id)
                )
                """
            )

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    def append_event(
        self, event_type: str, payload: dict[str, Any], run_id: str | None = None
    ) -> str:
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
        *,
        step_id: str,
        wait_type: WaitType,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        expires_at: str | None = None,
    ) -> str:
        return self.wait_store.create_wait(
            run_id,
            step_id=step_id,
            wait_type=wait_type,
            source_type=source_type,
            source_name=source_name,
            match_type=match_type,
            match_key=match_key,
            expires_at=expires_at,
        )

    def resolve_wait(self, wait_id: str) -> None:
        self.wait_store.resolve_wait(wait_id)

    def get_active_wait(
        self,
        run_id: str,
        step_id: str,
        *,
        wait_type: WaitType,
    ) -> dict[str, Any] | None:
        return self.wait_store.get_active_wait(run_id, step_id, wait_type=wait_type)

    def find_matching_waits(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
    ) -> list[dict[str, Any]]:
        return self.wait_store.find_matching_waits(
            source_type=source_type,
            source_name=source_name,
            match_type=match_type,
            match_key=match_key,
        )

    def create_external_event(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        payload: dict[str, Any],
        run_id: str | None = None,
        step_id: str | None = None,
        external_id: str | None = None,
        dedup_key: str | None = None,
    ) -> str:
        return self.external_event_store.create_external_event(
            source_type=source_type,
            source_name=source_name,
            match_type=match_type,
            match_key=match_key,
            payload=payload,
            run_id=run_id,
            step_id=step_id,
            external_id=external_id,
            dedup_key=dedup_key,
        )

    def get_latest_external_event(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        run_id: str | None = None,
        step_id: str | None = None,
        since_created_at: str | None = None,
    ) -> dict[str, Any] | None:
        return self.external_event_store.get_latest_external_event(
            source_type=source_type,
            source_name=source_name,
            match_type=match_type,
            match_key=match_key,
            run_id=run_id,
            step_id=step_id,
            since_created_at=since_created_at,
        )

    def register_external_receipt(
        self,
        dedup_key: str,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        payload: dict[str, Any],
    ) -> bool:
        return self.external_event_store.register_external_receipt(
            dedup_key,
            source_type,
            source_name,
            match_type,
            match_key,
            payload,
        )

    def consume_external_event(self, event_id: str, *, run_id: str) -> bool:
        return self.external_event_store.consume_external_event(event_id, run_id=run_id)

    def expire_active_waits_for_run(self, run_id: str) -> int:
        return self.wait_store.expire_active_waits_for_run(run_id)
