import json
import sqlite3
from pathlib import Path
from typing import Any

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunAgent, RunStatus
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType
from skiller.domain.wait.wait_type import WaitType
from skiller.infrastructure.db.sqlite_agent_context_store import ensure_agent_context_schema
from skiller.infrastructure.db.sqlite_repository import SqliteRepository
from skiller.infrastructure.db.sqlite_run_mapper import build_run_from_row
from skiller.infrastructure.db.sqlite_wait_store import SqliteWaitStore


class SqliteStateStore(SqliteRepository):
    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)
        self.wait_store = SqliteWaitStore(db_path)

    def init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY,
                  source TEXT NOT NULL,
                  ref TEXT NOT NULL,
                  snapshot_json TEXT NOT NULL,
                  status TEXT NOT NULL,
                  current TEXT,
                  inputs_json TEXT NOT NULL DEFAULT '{}',
                  step_executions_json TEXT NOT NULL DEFAULT '{}',
                  agents_json TEXT NOT NULL DEFAULT '{}',
                  steering_queue_json TEXT NOT NULL DEFAULT '[]',
                  cancel_reason TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS log_events (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  sequence INTEGER NOT NULL,
                  event_type TEXT NOT NULL,
                  step_id TEXT,
                  step_type TEXT,
                  agent_sequence INTEGER,
                  body_json TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(run_id, sequence),
                  FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
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
                CREATE INDEX IF NOT EXISTS idx_log_events_run_sequence
                  ON log_events(run_id, sequence);
                CREATE INDEX IF NOT EXISTS idx_log_events_run_type
                  ON log_events(run_id, event_type);
                CREATE INDEX IF NOT EXISTS idx_log_events_agent_sequence
                  ON log_events(run_id, agent_sequence);
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
    def create_run(
        self,
        source: str,
        ref: str,
        snapshot: dict[str, object],
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
                      source,
                      ref,
                      snapshot_json,
                      status,
                      current,
                      inputs_json,
                      step_executions_json,
                      agents_json,
                      steering_queue_json
                    )
                    VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        source,
                        ref,
                        json.dumps(snapshot),
                        RunStatus.CREATED.value,
                        json.dumps(context.inputs),
                        json.dumps(context.to_dict()["step_executions"]),
                        "{}",
                        json.dumps([item.to_dict() for item in context.steering_queue]),
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
                  source,
                  ref,
                  snapshot_json,
                  status,
                  current,
                  inputs_json,
                  step_executions_json,
                  agents_json,
                  steering_queue_json,
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

    def get_agent(
        self,
        *,
        run_id: str,
        agent_id: str,
    ) -> RunAgent | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT agents_json
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        agents = _agents_from_json(row["agents_json"])
        return agents.get(agent_id)

    def attach_agent(
        self,
        *,
        run_id: str,
        agent_id: str,
        context_id: str,
    ) -> None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT agents_json
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                return
            agents = _agents_from_json(row["agents_json"])
            agents[agent_id] = RunAgent(agent_id=agent_id, context_id=context_id)
            conn.execute(
                """
                UPDATE runs
                SET agents_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (_agents_to_json(agents), run_id),
            )

    def delete_run(self, run_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                return False

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
            conn.execute("DELETE FROM log_events WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        return True

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

    def expire_active_waits_for_run(self, run_id: str) -> int:
        return self.wait_store.expire_active_waits_for_run(run_id)


def _agents_from_json(raw_agents: object) -> dict[str, RunAgent]:
    if not isinstance(raw_agents, str) or not raw_agents.strip():
        return {}
    try:
        parsed = json.loads(raw_agents)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}

    agents: dict[str, RunAgent] = {}
    for raw_agent_id, raw_agent in parsed.items():
        agent_id = str(raw_agent_id).strip()
        if not agent_id or not isinstance(raw_agent, dict):
            continue
        context_id = raw_agent.get("context_id")
        agents[agent_id] = RunAgent(
            agent_id=agent_id,
            context_id=context_id if isinstance(context_id, str) else None,
        )
    return agents


def _agents_to_json(agents: dict[str, RunAgent]) -> str:
    return json.dumps(
        {
            agent_id: agent.to_dict()
            for agent_id, agent in agents.items()
        }
    )
