import json
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any

from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextPayload,
    agent_context_payload_from_dict,
    agent_context_payload_to_dict,
)
from skiller.domain.agent.llm_model import LLMUsage
from skiller.infrastructure.db.sqlite_repository import SqliteRepository


@dataclass(frozen=True)
class AgentContextWindowMarker:
    sequence: int
    window_tokens: int
    window_start_sequence: int


class SqliteAgentContextDatasource(SqliteRepository):
    def append_entry(
        self,
        *,
        run_id: str,
        context_id: str,
        entry_type: AgentContextEntryType,
        payload: AgentContextPayload,
        usage: LLMUsage | None = None,
        window_tokens: int | None = None,
        window_start_sequence: int | None = None,
        source_step_id: str,
    ) -> AgentContextEntry:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            sequence = self._next_sequence(conn, context_id=context_id)
            entry_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO agent_context_entries (
                  id,
                  run_id,
                  context_id,
                  sequence,
                  entry_type,
                  message_type,
                  window_tokens,
                  window_start_sequence,
                  payload_json,
                  usage_json,
                  source_step_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    run_id,
                    context_id,
                    sequence,
                    entry_type.value,
                    _message_type(payload),
                    window_tokens,
                    window_start_sequence,
                    json.dumps(agent_context_payload_to_dict(payload)),
                    json.dumps(_usage_to_dict(usage)) if usage is not None else None,
                    source_step_id,
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

    def list_entries(self, *, context_id: str) -> list[AgentContextEntry]:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            rows = conn.execute(
                """
                SELECT *
                FROM agent_context_entries
                WHERE context_id = ?
                ORDER BY sequence ASC
                """,
                (context_id,),
            ).fetchall()
        return [_build_entry(row) for row in rows]

    def list_entries_from_sequence(
        self,
        *,
        context_id: str,
        sequence: int,
    ) -> list[AgentContextEntry]:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            rows = conn.execute(
                """
                SELECT *
                FROM agent_context_entries
                WHERE context_id = ?
                  AND sequence >= ?
                ORDER BY sequence ASC
                """,
                (context_id, sequence),
            ).fetchall()
        return [_build_entry(row) for row in rows]

    def current_marker(
        self,
        *,
        context_id: str,
    ) -> AgentContextWindowMarker | None:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            row = conn.execute(
                """
                SELECT sequence, window_tokens, window_start_sequence
                FROM agent_context_entries
                WHERE context_id = ?
                  AND entry_type = ?
                  AND message_type = ?
                  AND window_tokens IS NOT NULL
                  AND window_start_sequence IS NOT NULL
                ORDER BY sequence DESC
                LIMIT 1
                """,
                (
                    context_id,
                    AgentContextEntryType.ASSISTANT_MESSAGE.value,
                    AgentAssistantMessageType.FINAL.value,
                ),
            ).fetchone()
        return _window_marker_from_row(row)

    def cutoff_marker(
        self,
        *,
        context_id: str,
        start_sequence: int,
        cutoff_tokens: int,
    ) -> AgentContextWindowMarker | None:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            row = conn.execute(
                """
                SELECT sequence, window_tokens, window_start_sequence
                FROM agent_context_entries
                WHERE context_id = ?
                  AND entry_type = ?
                  AND message_type = ?
                  AND sequence >= ?
                  AND window_tokens IS NOT NULL
                  AND window_start_sequence IS NOT NULL
                  AND window_tokens > ?
                ORDER BY sequence ASC
                LIMIT 1
                """,
                (
                    context_id,
                    AgentContextEntryType.ASSISTANT_MESSAGE.value,
                    AgentAssistantMessageType.FINAL.value,
                    start_sequence,
                    cutoff_tokens,
                ),
            ).fetchone()
        return _window_marker_from_row(row)

    def next_turn_id(self, *, context_id: str) -> str:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            row = conn.execute(
                """
                SELECT COUNT(*) AS turn_entries
                FROM agent_context_entries
                WHERE context_id = ?
                  AND entry_type IN (?, ?)
                """,
                (
                    context_id,
                    AgentContextEntryType.ASSISTANT_MESSAGE.value,
                    AgentContextEntryType.TOOL_CALL.value,
                ),
            ).fetchone()
        if row is None:
            return "turn-1"
        return f"turn-{int(row['turn_entries']) + 1}"

    def _next_sequence(
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
    ) -> int:
        row = conn.execute(
            """
            SELECT MAX(sequence) AS max_sequence
            FROM agent_context_entries
            WHERE context_id = ?
            """,
            (context_id,),
        ).fetchone()
        if row is None or row["max_sequence"] is None:
            return 1
        return int(row["max_sequence"]) + 1


def _window_marker_from_row(
    row: sqlite3.Row | None,
) -> AgentContextWindowMarker | None:
    if row is None:
        return None
    return AgentContextWindowMarker(
        sequence=int(row["sequence"]),
        window_tokens=int(row["window_tokens"]),
        window_start_sequence=int(row["window_start_sequence"]),
    )


def ensure_agent_context_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent_context_entries (
          id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          context_id TEXT NOT NULL,
          sequence INTEGER NOT NULL,
          entry_type TEXT NOT NULL,
          message_type TEXT NULL,
          window_tokens INTEGER NULL,
          window_start_sequence INTEGER NULL,
          payload_json TEXT NOT NULL,
          usage_json TEXT NULL,
          source_step_id TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(run_id) REFERENCES runs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_agent_context_entries_context
          ON agent_context_entries(context_id, sequence);

        CREATE INDEX IF NOT EXISTS idx_agent_context_entries_final_marker
          ON agent_context_entries(
            context_id,
            entry_type,
            message_type,
            window_tokens,
            sequence
          );

        """
    )


def _build_entry(row: sqlite3.Row) -> AgentContextEntry:
    raw_payload = json.loads(row["payload_json"])
    if not isinstance(raw_payload, dict):
        raw_payload = {}
    usage = _usage_from_json(row["usage_json"])
    entry_type = AgentContextEntryType(str(row["entry_type"]))
    return AgentContextEntry(
        id=str(row["id"]),
        run_id=str(row["run_id"]),
        context_id=str(row["context_id"]),
        sequence=int(row["sequence"]),
        entry_type=entry_type,
        message_type=_optional_assistant_message_type(row["message_type"]),
        window_tokens=_optional_int(row["window_tokens"]),
        window_start_sequence=_optional_int(row["window_start_sequence"]),
        payload=agent_context_payload_from_dict(
            entry_type=entry_type,
            value=_clone(raw_payload),
        ),
        usage=usage,
        source_step_id=str(row["source_step_id"]),
        created_at=str(row["created_at"]),
    )


def _usage_to_dict(usage: LLMUsage) -> dict[str, int | str | None]:
    result: dict[str, int | str | None] = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }
    if usage.provider is not None:
        result["provider"] = usage.provider.value
    if usage.model is not None:
        result["model"] = usage.model.value
    return result


def _message_type(payload: AgentContextPayload) -> str | None:
    if isinstance(payload, AgentAssistantMessagePayload):
        return payload.message_type.value
    return None


def _usage_from_json(raw_usage: object) -> LLMUsage | None:
    if not isinstance(raw_usage, str) or not raw_usage.strip():
        return None
    try:
        parsed = json.loads(raw_usage)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return LLMUsage(
        prompt_tokens=_optional_int(parsed.get("prompt_tokens")),
        completion_tokens=_optional_int(parsed.get("completion_tokens")),
        total_tokens=_optional_int(parsed.get("total_tokens")),
        provider=_optional_string(parsed.get("provider")),
        model=_optional_string(parsed.get("model")),
    )


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    return value


def _optional_assistant_message_type(
    value: object,
) -> AgentAssistantMessageType | None:
    value = _optional_string(value)
    if value is None:
        return None
    return AgentAssistantMessageType(value)


def _clone(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value
