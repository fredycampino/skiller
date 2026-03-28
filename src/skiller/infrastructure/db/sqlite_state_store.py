import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import Run, RunStatus
from skiller.infrastructure.db.sqlite_repository import SqliteRepository


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
                  results_json TEXT NOT NULL DEFAULT '{}',
                  steering_messages_json TEXT NOT NULL DEFAULT '[]',
                  cancel_reason TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS waits (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  step_id TEXT NOT NULL,
                  webhook TEXT NOT NULL,
                  key TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  expires_at TEXT,
                  resolved_at TEXT,
                  FOREIGN KEY(run_id) REFERENCES runs(id)
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

                CREATE TABLE IF NOT EXISTS webhook_events (
                  id TEXT PRIMARY KEY,
                  webhook TEXT NOT NULL,
                  key TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  dedup_key TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS input_waits (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  step_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  resolved_at TEXT,
                  FOREIGN KEY(run_id) REFERENCES runs(id)
                );

                CREATE TABLE IF NOT EXISTS input_events (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  step_id TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(run_id) REFERENCES runs(id)
                );

                CREATE TABLE IF NOT EXISTS webhook_registrations (
                  webhook TEXT PRIMARY KEY,
                  secret TEXT NOT NULL,
                  enabled INTEGER NOT NULL DEFAULT 1,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_runs_status_updated_at ON runs(status, updated_at);
                CREATE INDEX IF NOT EXISTS idx_waits_run_status ON waits(run_id, status);
                CREATE INDEX IF NOT EXISTS idx_waits_webhook_key_status
                  ON waits(webhook, key, status);
                CREATE INDEX IF NOT EXISTS idx_events_run_created_at
                  ON events(run_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_webhook_receipts_webhook_key_created_at
                  ON webhook_receipts(webhook, key, created_at);
                CREATE INDEX IF NOT EXISTS idx_webhook_events_webhook_key_created_at
                  ON webhook_events(webhook, key, created_at);
                CREATE INDEX IF NOT EXISTS idx_input_waits_run_step_status
                  ON input_waits(run_id, step_id, status);
                CREATE INDEX IF NOT EXISTS idx_input_events_run_step_created_at
                  ON input_events(run_id, step_id, created_at);
                """
            )
            self._ensure_runs_current_column(conn)
            self._ensure_runs_results_column(conn)
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
                      results_json,
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
                        json.dumps(context.results),
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
            updates.append("results_json = ?")
            params.append(json.dumps(context.results))
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
                  results_json,
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
        return self._build_run_from_row(row)

    def list_runs(self, *, limit: int = 20, statuses: list[str] | None = None) -> list[Run]:
        normalized_limit = max(1, limit)
        normalized_statuses = [
            status.strip().upper()
            for status in statuses or []
            if status.strip()
        ]
        query = """
            SELECT
              id,
              skill_source,
              skill_ref,
              skill_snapshot_json,
              status,
              current,
              inputs_json,
              results_json,
              steering_messages_json,
              cancel_reason,
              created_at,
              updated_at
            FROM runs
        """
        params: list[Any] = []
        if normalized_statuses:
            placeholders = ", ".join("?" for _ in normalized_statuses)
            query += f" WHERE status IN ({placeholders})"
            params.extend(normalized_statuses)
        query += """
            ORDER BY updated_at DESC, rowid DESC
            LIMIT ?
        """
        params.append(normalized_limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._build_run_from_row(row) for row in rows]

    def _ensure_runs_current_column(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(runs)").fetchall()
        column_names = {str(row["name"]) for row in rows}
        if "current" in column_names:
            return
        conn.execute("ALTER TABLE runs ADD COLUMN current TEXT")

    def _ensure_runs_results_column(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(runs)").fetchall()
        column_names = {str(row["name"]) for row in rows}
        if "results_json" in column_names:
            return
        conn.execute("ALTER TABLE runs ADD COLUMN results_json TEXT NOT NULL DEFAULT '{}'")

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

    def _build_run_from_row(self, row: sqlite3.Row) -> Run:
        skill_snapshot = json.loads(row["skill_snapshot_json"])
        if not isinstance(skill_snapshot, dict):
            skill_snapshot = {}
        inputs_dict = json.loads(row["inputs_json"])
        if not isinstance(inputs_dict, dict):
            inputs_dict = {}
        results_dict = json.loads(row["results_json"])
        if not isinstance(results_dict, dict):
            results_dict = {}
        steering_messages = json.loads(row["steering_messages_json"])
        if not isinstance(steering_messages, list):
            steering_messages = []
        run_id = str(row["id"])
        context = self._build_context(
            inputs=inputs_dict,
            results=results_dict,
            steering_messages=steering_messages,
            cancel_reason=row["cancel_reason"],
        )

        return Run(
            id=run_id,
            skill_source=row["skill_source"],
            skill_ref=row["skill_ref"],
            skill_snapshot=skill_snapshot,
            status=row["status"],
            current=(str(row["current"]) if row["current"] is not None else None),
            context=context,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

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
        webhook: str,
        key: str,
        *,
        step_id: str | None = None,
        expires_at: str | None = None,
    ) -> str:
        wait_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO waits (id, run_id, step_id, webhook, key, status, expires_at)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?)
                """,
                (wait_id, run_id, step_id or "", webhook, key, expires_at),
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

    def get_active_wait(self, run_id: str, step_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                  id,
                  run_id,
                  step_id,
                  webhook,
                  key,
                  status,
                  created_at,
                  resolved_at,
                  expires_at
                FROM waits
                WHERE run_id = ? AND step_id = ? AND status = 'ACTIVE'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (run_id, step_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "step_id": row["step_id"],
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
                  webhook,
                  key,
                  status,
                  created_at,
                  resolved_at,
                  expires_at
                FROM waits
                WHERE webhook = ? AND key = ? AND status = 'ACTIVE'
                ORDER BY created_at ASC
                """,
                (webhook, key),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "step_id": row["step_id"],
                "webhook": row["webhook"],
                "key": row["key"],
                "status": row["status"],
                "created_at": row["created_at"],
                "resolved_at": row["resolved_at"],
                "expires_at": row["expires_at"],
            }
            for row in rows
        ]

    def create_webhook_event(
        self, webhook: str, key: str, payload: dict[str, Any], dedup_key: str
    ) -> str:
        event_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO webhook_events (id, webhook, key, payload_json, dedup_key)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, webhook, key, json.dumps(payload), dedup_key),
            )
        return event_id

    def create_input_wait(self, run_id: str, step_id: str) -> str:
        wait_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO input_waits (id, run_id, step_id, status)
                VALUES (?, ?, ?, 'ACTIVE')
                """,
                (wait_id, run_id, step_id),
            )
        return wait_id

    def resolve_input_wait(self, wait_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE input_waits
                SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (wait_id,),
            )

    def get_active_input_wait(self, run_id: str, step_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, run_id, step_id, status, created_at, resolved_at
                FROM input_waits
                WHERE run_id = ? AND step_id = ? AND status = 'ACTIVE'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (run_id, step_id),
            ).fetchone()

        if row is None:
            return None

        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "step_id": row["step_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "resolved_at": row["resolved_at"],
        }

    def create_input_event(self, run_id: str, step_id: str, payload: dict[str, Any]) -> str:
        event_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO input_events (id, run_id, step_id, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, run_id, step_id, json.dumps(payload)),
            )
        return event_id

    def get_latest_input_event(
        self,
        run_id: str,
        step_id: str,
        *,
        since_created_at: str | None = None,
    ) -> dict[str, Any] | None:
        if since_created_at:
            query = """
                SELECT id, run_id, step_id, payload_json, created_at
                FROM input_events
                WHERE run_id = ? AND step_id = ? AND created_at >= ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
            """
            params: tuple[Any, ...] = (run_id, step_id, since_created_at)
        else:
            query = """
                SELECT id, run_id, step_id, payload_json, created_at
                FROM input_events
                WHERE run_id = ? AND step_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
            """
            params = (run_id, step_id)

        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()

        if row is None:
            return None

        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            payload = {}

        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "step_id": row["step_id"],
            "payload": payload,
            "created_at": row["created_at"],
        }

    def get_latest_webhook_event(
        self,
        webhook: str,
        key: str,
        *,
        since_created_at: str | None = None,
    ) -> dict[str, Any] | None:
        if since_created_at:
            query = """
                SELECT id, webhook, key, payload_json, dedup_key, created_at
                FROM webhook_events
                WHERE webhook = ? AND key = ? AND created_at >= ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
            """
            params: tuple[Any, ...] = (webhook, key, since_created_at)
        else:
            query = """
                SELECT id, webhook, key, payload_json, dedup_key, created_at
                FROM webhook_events
                WHERE webhook = ? AND key = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
            """
            params = (webhook, key)

        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()

        if row is None:
            return None

        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            payload = {}

        return {
            "id": row["id"],
            "webhook": row["webhook"],
            "key": row["key"],
            "payload": payload,
            "dedup_key": row["dedup_key"],
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
            webhook_result = conn.execute(
                """
                UPDATE waits
                SET status = 'EXPIRED', resolved_at = CURRENT_TIMESTAMP
                WHERE run_id = ? AND status = 'ACTIVE'
                """,
                (run_id,),
            )
            input_result = conn.execute(
                """
                UPDATE input_waits
                SET status = 'EXPIRED', resolved_at = CURRENT_TIMESTAMP
                WHERE run_id = ? AND status = 'ACTIVE'
                """,
                (run_id,),
            )
            return webhook_result.rowcount + input_result.rowcount

    def _build_context(
        self,
        *,
        inputs: dict[str, Any],
        results: dict[str, Any],
        steering_messages: list[str],
        cancel_reason: str | None,
    ) -> RunContext:
        context = RunContext(
            inputs=inputs,
            results=results if isinstance(results, dict) else {},
            steering_messages=steering_messages if isinstance(steering_messages, list) else [],
        )
        if isinstance(cancel_reason, str) and cancel_reason.strip():
            context.cancel_reason = cancel_reason

        return context
