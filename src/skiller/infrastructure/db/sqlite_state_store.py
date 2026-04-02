import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from skiller.domain.external_event_type import ExternalEventType
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import Run, RunStatus
from skiller.domain.wait_type import WaitType
from skiller.infrastructure.db.sqlite_repository import SqliteRepository
from skiller.infrastructure.db.sqlite_run_mapper import build_run_from_row


class SqliteStateStore(SqliteRepository):
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

                CREATE TABLE IF NOT EXISTS webhook_receipts (
                  dedup_key TEXT PRIMARY KEY,
                  webhook TEXT NOT NULL,
                  key TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_runs_status_updated_at ON runs(status, updated_at);
                CREATE INDEX IF NOT EXISTS idx_events_run_created_at
                  ON events(run_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_webhook_receipts_webhook_key_created_at
                  ON webhook_receipts(webhook, key, created_at);
                """
            )
            self._ensure_waits_table(conn)
            self._ensure_external_events_table(conn)
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_waits_run_step_type_status
                  ON waits(run_id, step_id, wait_type, status)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_waits_webhook_key_type_status
                  ON waits(webhook, key, wait_type, status)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_external_events_run_step_type_created_at
                  ON external_events(event_type, run_id, step_id, created_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_external_events_webhook_key_type_created_at
                  ON external_events(event_type, webhook, key, created_at)
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
        if status in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED):
            updates.append("finished_at = CURRENT_TIMESTAMP")

        if not updates:
            return

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(run_id)

        query = f"UPDATE runs SET {', '.join(updates)} WHERE id = ?"
        with self._connect() as conn:
            conn.execute(query, params)

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
                  webhook TEXT,
                  key TEXT,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  expires_at TEXT,
                  resolved_at TEXT,
                  FOREIGN KEY(run_id) REFERENCES runs(id)
                )
                """
            )
            return

        rows = conn.execute("PRAGMA table_info(waits)").fetchall()
        column_names = {str(row["name"]) for row in rows}
        if "wait_type" in column_names:
            conn.execute("DROP TABLE IF EXISTS input_waits")
            return

        conn.execute(
            """
            CREATE TABLE waits_new (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              step_id TEXT NOT NULL,
              wait_type TEXT NOT NULL,
              webhook TEXT,
              key TEXT,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              expires_at TEXT,
              resolved_at TEXT,
              FOREIGN KEY(run_id) REFERENCES runs(id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO waits_new (
              id,
              run_id,
              step_id,
              wait_type,
              webhook,
              key,
              status,
              created_at,
              expires_at,
              resolved_at
            )
            SELECT
              id,
              run_id,
              step_id,
              ?,
              webhook,
              key,
              status,
              created_at,
              expires_at,
              resolved_at
            FROM waits
            """,
            (WaitType.WEBHOOK.value,),
        )
        if self._table_exists(conn, "input_waits"):
            conn.execute(
                """
                INSERT INTO waits_new (
                  id,
                  run_id,
                  step_id,
                  wait_type,
                  webhook,
                  key,
                  status,
                  created_at,
                  expires_at,
                  resolved_at
                )
                SELECT
                  id,
                  run_id,
                  step_id,
                  ?,
                  NULL,
                  NULL,
                  status,
                  created_at,
                  NULL,
                  resolved_at
                FROM input_waits
                """,
                (WaitType.INPUT.value,),
            )
        conn.execute("DROP TABLE waits")
        conn.execute("ALTER TABLE waits_new RENAME TO waits")
        conn.execute("DROP TABLE IF EXISTS input_waits")

    def _ensure_external_events_table(self, conn: sqlite3.Connection) -> None:
        if not self._table_exists(conn, "external_events"):
            conn.execute(
                """
                CREATE TABLE external_events (
                  id TEXT PRIMARY KEY,
                  event_type TEXT NOT NULL,
                  run_id TEXT,
                  step_id TEXT,
                  webhook TEXT,
                  key TEXT,
                  dedup_key TEXT,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(run_id) REFERENCES runs(id)
                )
                """
            )

        if self._table_exists(conn, "input_events"):
            conn.execute(
                """
                INSERT INTO external_events (
                  id,
                  event_type,
                  run_id,
                  step_id,
                  webhook,
                  key,
                  dedup_key,
                  payload_json,
                  created_at
                )
                SELECT
                  id,
                  ?,
                  run_id,
                  step_id,
                  NULL,
                  NULL,
                  NULL,
                  payload_json,
                  created_at
                FROM input_events
                """,
                (ExternalEventType.INPUT.value,),
            )
            conn.execute("DROP TABLE input_events")

        if self._table_exists(conn, "webhook_events"):
            conn.execute(
                """
                INSERT INTO external_events (
                  id,
                  event_type,
                  run_id,
                  step_id,
                  webhook,
                  key,
                  dedup_key,
                  payload_json,
                  created_at
                )
                SELECT
                  id,
                  ?,
                  NULL,
                  NULL,
                  webhook,
                  key,
                  dedup_key,
                  payload_json,
                  created_at
                FROM webhook_events
                """,
                (ExternalEventType.WEBHOOK.value,),
            )
            conn.execute("DROP TABLE webhook_events")

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
        webhook: str | None = None,
        key: str | None = None,
        expires_at: str | None = None,
    ) -> str:
        wait_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO waits (id, run_id, step_id, wait_type, webhook, key, status, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
                """,
                (wait_id, run_id, step_id, wait_type.value, webhook, key, expires_at),
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

    def get_active_wait(
        self,
        run_id: str,
        step_id: str,
        *,
        wait_type: WaitType,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                  id,
                  run_id,
                  step_id,
                  wait_type,
                  webhook,
                  key,
                  status,
                  created_at,
                  resolved_at,
                  expires_at
                FROM waits
                WHERE run_id = ? AND step_id = ? AND wait_type = ? AND status = 'ACTIVE'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (run_id, step_id, wait_type.value),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "step_id": row["step_id"],
            "wait_type": row["wait_type"],
            "webhook": row["webhook"],
            "key": row["key"],
            "status": row["status"],
            "created_at": row["created_at"],
            "resolved_at": row["resolved_at"],
            "expires_at": row["expires_at"],
        }

    def find_matching_waits(self, webhook: str, key: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  id,
                  run_id,
                  step_id,
                  wait_type,
                  webhook,
                  key,
                  status,
                  created_at,
                  resolved_at,
                  expires_at
                FROM waits
                WHERE webhook = ? AND key = ? AND wait_type = ? AND status = 'ACTIVE'
                ORDER BY created_at ASC
                """,
                (webhook, key, WaitType.WEBHOOK.value),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "step_id": row["step_id"],
                "wait_type": row["wait_type"],
                "webhook": row["webhook"],
                "key": row["key"],
                "status": row["status"],
                "created_at": row["created_at"],
                "resolved_at": row["resolved_at"],
                "expires_at": row["expires_at"],
            }
            for row in rows
        ]

    def create_external_event(
        self,
        *,
        event_type: ExternalEventType,
        payload: dict[str, Any],
        run_id: str | None = None,
        step_id: str | None = None,
        webhook: str | None = None,
        key: str | None = None,
        dedup_key: str | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO external_events (
                  id,
                  event_type,
                  run_id,
                  step_id,
                  webhook,
                  key,
                  dedup_key,
                  payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event_type.value,
                    run_id,
                    step_id,
                    webhook,
                    key,
                    dedup_key,
                    json.dumps(payload),
                ),
            )
        return event_id

    def get_latest_external_event(
        self,
        *,
        event_type: ExternalEventType,
        run_id: str | None = None,
        step_id: str | None = None,
        webhook: str | None = None,
        key: str | None = None,
        since_created_at: str | None = None,
    ) -> dict[str, Any] | None:
        if event_type == ExternalEventType.INPUT:
            if not run_id or not step_id:
                raise ValueError("input external events require run_id and step_id")
            query = """
                SELECT
                    id,
                    event_type,
                    run_id,
                    step_id,
                    webhook,
                    key,
                    dedup_key,
                    payload_json,
                    created_at
                FROM external_events
                WHERE event_type = ? AND run_id = ? AND step_id = ?
            """
            params: list[Any] = [event_type.value, run_id, step_id]
        else:
            if not webhook or not key:
                raise ValueError("webhook external events require webhook and key")
            query = """
                SELECT
                    id,
                    event_type,
                    run_id,
                    step_id,
                    webhook,
                    key,
                    dedup_key,
                    payload_json,
                    created_at
                FROM external_events
                WHERE event_type = ? AND webhook = ? AND key = ?
            """
            params = [event_type.value, webhook, key]

        if since_created_at:
            query += " AND created_at >= ?"
            params.append(since_created_at)

        query += " ORDER BY created_at DESC, rowid DESC LIMIT 1"

        with self._connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()

        if row is None:
            return None

        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            payload = {}

        return {
            "id": row["id"],
            "event_type": row["event_type"],
            "run_id": row["run_id"],
            "step_id": row["step_id"],
            "webhook": row["webhook"],
            "key": row["key"],
            "dedup_key": row["dedup_key"],
            "payload": payload,
            "created_at": row["created_at"],
        }

    def register_webhook_receipt(
        self, dedup_key: str, webhook: str, key: str, payload: dict[str, Any]
    ) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO webhook_receipts (dedup_key, webhook, key, payload_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (dedup_key, webhook, key, json.dumps(payload)),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def expire_active_waits_for_run(self, run_id: str) -> int:
        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE waits
                SET status = 'EXPIRED', resolved_at = CURRENT_TIMESTAMP
                WHERE run_id = ? AND status = 'ACTIVE'
                """,
                (run_id,),
            )
            return result.rowcount
