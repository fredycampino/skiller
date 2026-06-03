import json
import sqlite3
import uuid
from typing import Any

from skiller.domain.event.event_model import (
    RuntimeEvent,
    RuntimeEventDraft,
    RuntimeEventType,
    runtime_event_agent_sequence,
    runtime_event_payload_from_dict,
    runtime_event_payload_to_dict,
    runtime_event_step_id,
    runtime_event_step_type,
)
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort
from skiller.infrastructure.db.sqlite_repository import SqliteRepository


class SqliteRuntimeEventStore(SqliteRepository, RuntimeEventStorePort):
    def append_event(self, event: RuntimeEventDraft) -> str:
        event_id = str(uuid.uuid4())
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence
                FROM log_events
                WHERE run_id = ?
                """,
                (event.run_id,),
            ).fetchone()
            sequence = int(row["next_sequence"]) if row is not None else 1
            conn.execute(
                """
                INSERT INTO log_events (
                  id,
                  run_id,
                  sequence,
                  event_type,
                  step_id,
                  step_type,
                  agent_sequence,
                  body_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event.run_id,
                    sequence,
                    event.type.value,
                    event.step_id
                    if event.step_id is not None
                    else runtime_event_step_id(event.payload),
                    event.step_type
                    if event.step_type is not None
                    else runtime_event_step_type(event.payload),
                    event.agent_sequence
                    if event.agent_sequence is not None
                    else runtime_event_agent_sequence(event.payload),
                    json.dumps(runtime_event_payload_to_dict(event.payload)),
                ),
            )
        return event_id

    def list_events(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[RuntimeEvent]:
        query = """
            SELECT
              sequence,
              id,
              run_id,
              event_type,
              step_id,
              step_type,
              agent_sequence,
              body_json,
              created_at
            FROM log_events
            WHERE run_id = ?
        """
        params: list[Any] = [run_id]
        if after_sequence is not None:
            query += " AND sequence > ?"
            params.append(after_sequence)
        query += " ORDER BY sequence ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._build_runtime_event(row) for row in rows]

    def get_last_event(self, run_id: str) -> RuntimeEvent | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                  sequence,
                  id,
                  run_id,
                  event_type,
                  step_id,
                  step_type,
                  agent_sequence,
                  body_json,
                  created_at
                FROM log_events
                WHERE run_id = ?
                ORDER BY sequence DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return self._build_runtime_event(row)

    def _build_runtime_event(self, row: sqlite3.Row) -> RuntimeEvent:
        return RuntimeEvent(
            sequence=int(row["sequence"]),
            id=row["id"],
            run_id=row["run_id"],
            type=RuntimeEventType(row["event_type"]),
            step_id=row["step_id"],
            step_type=row["step_type"],
            agent_sequence=row["agent_sequence"],
            created_at=row["created_at"],
            payload=runtime_event_payload_from_dict(
                event_type=RuntimeEventType(row["event_type"]),
                value={
                    **json.loads(row["body_json"]),
                    "step_id": row["step_id"],
                    "step_type": row["step_type"],
                    "agent_sequence": row["agent_sequence"],
                },
            ),
        )
