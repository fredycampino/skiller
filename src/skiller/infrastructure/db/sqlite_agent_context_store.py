import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from skiller.domain.agent.agent_context_model import AgentContextEntry, AgentContextEntryType
from skiller.infrastructure.db.sqlite_repository import SqliteRepository


class SqliteAgentContextStore(SqliteRepository):
    def init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            ensure_agent_context_schema(conn)

    def append_entry(
        self,
        *,
        run_id: str,
        context_id: str,
        entry_type: AgentContextEntryType,
        payload: dict[str, object],
        source_step_id: str,
        idempotency_key: str,
    ) -> AgentContextEntry:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            row = conn.execute(
                """
                SELECT *
                FROM agent_context_entries
                WHERE run_id = ? AND context_id = ? AND idempotency_key = ?
                """,
                (run_id, context_id, idempotency_key),
            ).fetchone()
            if row is not None:
                return _build_entry(row)

            sequence = self._next_sequence(conn, run_id=run_id, context_id=context_id)
            entry_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO agent_context_entries (
                  id,
                  run_id,
                  context_id,
                  sequence,
                  entry_type,
                  payload_json,
                  source_step_id,
                  idempotency_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    run_id,
                    context_id,
                    sequence,
                    entry_type.value,
                    json.dumps(payload),
                    source_step_id,
                    idempotency_key,
                ),
            )
            row = conn.execute(
                """
                SELECT *
                FROM agent_context_entries
                WHERE id = ?
                """,
                (entry_id,),
            ).fetchone()
        if row is None:
            raise ValueError("Agent context entry was not persisted")
        return _build_entry(row)

    def list_entries(self, *, run_id: str, context_id: str) -> list[AgentContextEntry]:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            rows = conn.execute(
                """
                SELECT *
                FROM agent_context_entries
                WHERE run_id = ? AND context_id = ?
                ORDER BY sequence ASC
                """,
                (run_id, context_id),
            ).fetchall()
        return [_build_entry(row) for row in rows]

    def _next_sequence(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: str,
        context_id: str,
    ) -> int:
        row = conn.execute(
            """
            SELECT MAX(sequence) AS max_sequence
            FROM agent_context_entries
            WHERE run_id = ? AND context_id = ?
            """,
            (run_id, context_id),
        ).fetchone()
        if row is None or row["max_sequence"] is None:
            return 1
        return int(row["max_sequence"]) + 1


def ensure_agent_context_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent_context_entries (
          id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          context_id TEXT NOT NULL,
          sequence INTEGER NOT NULL,
          entry_type TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          source_step_id TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(run_id) REFERENCES runs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_agent_context_entries_context
          ON agent_context_entries(run_id, context_id, sequence);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_context_entries_idempotency
          ON agent_context_entries(run_id, context_id, idempotency_key);
        """
    )


def _build_entry(row: sqlite3.Row) -> AgentContextEntry:
    payload = json.loads(row["payload_json"])
    if not isinstance(payload, dict):
        payload = {}
    return AgentContextEntry(
        id=str(row["id"]),
        run_id=str(row["run_id"]),
        context_id=str(row["context_id"]),
        sequence=int(row["sequence"]),
        entry_type=AgentContextEntryType(str(row["entry_type"])),
        payload=_clone(payload),
        source_step_id=str(row["source_step_id"]),
        idempotency_key=str(row["idempotency_key"]),
        created_at=str(row["created_at"]),
    )


def _clone(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value
