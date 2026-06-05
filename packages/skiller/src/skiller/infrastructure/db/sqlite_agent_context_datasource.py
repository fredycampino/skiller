import json
import sqlite3
import uuid
from typing import Any

from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextPayload,
    AgentContextUsageMarker,
    agent_context_payload_from_dict,
    agent_context_payload_to_dict,
)
from skiller.domain.agent.agent_llm_provider_model import (
    AgentLLMModel,
    agent_llm_model_from_value,
)
from skiller.domain.agent.agent_stats_model import (
    AgentContextObservedStats,
    AgentContextObservedWindowStats,
)
from skiller.domain.agent.llm_model import LLMUsage
from skiller.infrastructure.db.sqlite_repository import SqliteRepository

_WINDOW_ENTRY_PAGE_SIZE = 100


class SqliteAgentContextDatasource(SqliteRepository):
    def append_entry(
        self,
        *,
        run_id: str,
        context_id: str,
        entry_type: AgentContextEntryType,
        payload: AgentContextPayload,
        usage: LLMUsage | None = None,
        window_start_sequence: int | None = None,
        delta_tokens: int | None = None,
        window_base: bool | None = None,
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
                  window_start_sequence,
                  delta_tokens,
                  window_base,
                  payload_json,
                  usage_json,
                  source_step_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    run_id,
                    context_id,
                    sequence,
                    entry_type.value,
                    _message_type(payload),
                    window_start_sequence,
                    delta_tokens,
                    _bool_to_int(window_base),
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

    def list_window_entries(
        self,
        *,
        context_id: str,
        window_width_tokens: int,
    ) -> list[AgentContextEntry]:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            entries: list[AgentContextEntry] = []
            total_tokens = 0
            before_sequence: int | None = None
            while True:
                rows = self._window_entry_page(
                    conn,
                    context_id=context_id,
                    before_sequence=before_sequence,
                )
                if not rows:
                    break

                for row in rows:
                    delta_tokens = _optional_int(row["delta_tokens"]) or 0
                    if delta_tokens < 0:
                        delta_tokens = 0
                    if (
                        entries
                        and total_tokens + delta_tokens > window_width_tokens
                    ):
                        return list(reversed(entries))
                    entries.append(_build_entry(row))
                    total_tokens += delta_tokens

                before_sequence = int(rows[-1]["sequence"])
        return list(reversed(entries))

    def get_last_usage_marker(
        self,
        *,
        context_id: str,
    ) -> AgentContextUsageMarker | None:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            return self._last_usage_marker(conn, context_id=context_id)

    def get_observed_stats(
        self,
        *,
        context_id: str,
    ) -> AgentContextObservedStats:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            totals = conn.execute(
                """
                SELECT COUNT(*) AS entries,
                       COALESCE(MIN(sequence), 0) AS start_sequence,
                       COALESCE(MAX(sequence), 0) AS end_sequence,
                       COALESCE(SUM(delta_tokens), 0) AS estimated_tokens
                FROM agent_context_entries
                WHERE context_id = ?
                """,
                (context_id,),
            ).fetchone()
            if totals is None:
                return _empty_observed_stats()

            marker = self._last_usage_marker(conn, context_id=context_id)
            window_start_sequence = (
                marker.window_start_sequence
                if marker is not None
                else int(totals["start_sequence"])
            )
            current_tokens = 0
            if marker is not None:
                current_row = conn.execute(
                    """
                    SELECT COALESCE(SUM(delta_tokens), 0) AS current_tokens
                    FROM agent_context_entries
                    WHERE context_id = ?
                      AND sequence >= ?
                    """,
                    (context_id, window_start_sequence),
                ).fetchone()
                if current_row is not None:
                    current_tokens = int(current_row["current_tokens"])

        return AgentContextObservedStats(
            entries=int(totals["entries"]),
            estimated_tokens=int(totals["estimated_tokens"]),
            window=AgentContextObservedWindowStats(
                start_sequence=window_start_sequence,
                end_sequence=int(totals["end_sequence"]),
                current_tokens=current_tokens,
            ),
        )

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

    def _last_usage_marker(
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
    ) -> AgentContextUsageMarker | None:
        rows = conn.execute(
            """
            SELECT sequence,
                   usage_json,
                   delta_tokens,
                   window_start_sequence,
                   window_base
            FROM agent_context_entries
            WHERE context_id = ?
              AND usage_json IS NOT NULL
              AND delta_tokens IS NOT NULL
              AND window_start_sequence IS NOT NULL
              AND window_base IS NOT NULL
            ORDER BY sequence DESC
            """,
            (context_id,),
        ).fetchall()
        for row in rows:
            usage = _usage_from_json(row["usage_json"])
            if usage is None or usage.prompt_tokens is None:
                continue
            return AgentContextUsageMarker(
                sequence=int(row["sequence"]),
                prompt_tokens=usage.prompt_tokens,
                delta_tokens=int(row["delta_tokens"]),
                window_start_sequence=int(row["window_start_sequence"]),
                window_base=bool(row["window_base"]),
            )
        return None

    def _window_entry_page(
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
        before_sequence: int | None,
    ) -> list[sqlite3.Row]:
        if before_sequence is None:
            return conn.execute(
                """
                SELECT *
                FROM agent_context_entries
                WHERE context_id = ?
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (context_id, _WINDOW_ENTRY_PAGE_SIZE),
            ).fetchall()

        return conn.execute(
            """
            SELECT *
            FROM agent_context_entries
            WHERE context_id = ?
              AND sequence < ?
            ORDER BY sequence DESC
            LIMIT ?
            """,
            (context_id, before_sequence, _WINDOW_ENTRY_PAGE_SIZE),
        ).fetchall()


def ensure_agent_context_schema(conn: sqlite3.Connection) -> None:
    _create_agent_context_entries(conn)
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_context_entries_context
          ON agent_context_entries(context_id, sequence)
        """,
    )


def _create_agent_context_entries(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_context_entries (
          id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          context_id TEXT NOT NULL,
          sequence INTEGER NOT NULL,
          entry_type TEXT NOT NULL,
          message_type TEXT NULL,
          window_start_sequence INTEGER NULL,
          delta_tokens INTEGER NULL,
          window_base INTEGER NULL,
          payload_json TEXT NOT NULL,
          usage_json TEXT NULL,
          source_step_id TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(run_id) REFERENCES runs(id)
        )
        """,
    )


def _empty_observed_stats() -> AgentContextObservedStats:
    return AgentContextObservedStats(
        entries=0,
        estimated_tokens=0,
        window=AgentContextObservedWindowStats(
            start_sequence=0,
            end_sequence=0,
            current_tokens=0,
        ),
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
        window_start_sequence=_optional_int(row["window_start_sequence"]),
        delta_tokens=_optional_int(row["delta_tokens"]),
        window_base=_optional_bool(row["window_base"]),
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


def _bool_to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


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
        model=_optional_model(parsed.get("model")),
    )


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return None


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    return value


def _optional_model(value: object) -> AgentLLMModel | None:
    value = _optional_string(value)
    if value is None:
        return None
    try:
        return agent_llm_model_from_value(value)
    except ValueError:
        return None


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
