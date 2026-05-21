import json
import sqlite3
import uuid
from typing import Any

from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextPayload,
    AgentToolCallPayload,
    AgentToolResultPayload,
    AgentUserMessagePayload,
    agent_context_payload_from_dict,
    agent_context_payload_to_dict,
)
from skiller.domain.agent.agent_context_stats_port import AgentContextStatsPort
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.agent_run_identity import AgentContext
from skiller.domain.agent.agent_stats_model import (
    AgentContextEntryStats,
    AgentContextStats,
    AgentContextUsageStats,
)
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult
from skiller.infrastructure.db.sqlite_repository import SqliteRepository


class SqliteAgentContextStore(
    SqliteRepository,
    AgentContextStorePort,
    AgentContextStatsPort,
):
    def append_user_message(
        self,
        *,
        context: AgentContext,
        text: str,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload=AgentUserMessagePayload(text=text),
            source_step_id=context.agent_id,
        )

    def append_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        message_type: str,
        text: str,
        usage: LLMUsage | None = None,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload=AgentAssistantMessagePayload(
                turn_id=turn_id,
                message_type=message_type,
                text=text,
                total_tokens=usage.total_tokens if usage is not None else 0,
            ),
            usage=usage,
            source_step_id=context.agent_id,
        )

    def append_tool_call(
        self,
        *,
        context: AgentContext,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload=AgentToolCallPayload(
                turn_id=tool_call.turn_id,
                parent_sequence=tool_call.parent_sequence,
                tool_call_id=tool_call.tool_call_id,
                tool=tool_call.tool,
                args=tool_call.args,
            ),
            source_step_id=context.agent_id,
        )

    def append_tool_result(
        self,
        *,
        context: AgentContext,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry:
        result = tool_result.result
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload=AgentToolResultPayload(
                turn_id=tool_result.turn_id,
                parent_sequence=tool_result.parent_sequence,
                tool_call_id=tool_result.tool_call_id,
                tool=result.name,
                status=result.status.value,
                data=result.data,
                text=result.text,
                error=result.error,
            ),
            source_step_id=context.agent_id,
        )

    def _append_entry(
        self,
        *,
        run_id: str,
        context_id: str,
        entry_type: AgentContextEntryType,
        payload: AgentContextPayload,
        usage: LLMUsage | None = None,
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
                  total_tokens,
                  payload_json,
                  usage_json,
                  source_step_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    run_id,
                    context_id,
                    sequence,
                    entry_type.value,
                    _message_type(payload),
                    _total_tokens(payload),
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
            return _list_entries(conn, context_id=context_id)

    def list_context_window(
        self,
        *,
        context_id: str,
        window_tokens: int,
    ) -> list[AgentContextEntry]:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            current_total = _current_total_tokens(conn, context_id=context_id)
            if current_total is None or current_total <= window_tokens:
                return _list_entries(conn, context_id=context_id)

            marker_sequence = _window_marker_sequence(
                conn,
                context_id=context_id,
                cutoff=current_total - window_tokens,
            )
            if marker_sequence is None:
                return _list_entries(conn, context_id=context_id)

            return _list_entries_from_sequence(
                conn,
                context_id=context_id,
                sequence=marker_sequence,
            )

    def get_stats(self, *, context_id: str) -> AgentContextStats:
        entries = self.list_entries(context_id=context_id)
        return AgentContextStats(
            entries=_calculate_entry_stats(entries),
            usage=_calculate_usage_stats(entries),
        )

    def get_usage(self, *, context_id: str) -> LLMUsage:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            usage = _last_final_usage(conn, context_id=context_id)
        return usage or _empty_usage()

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
          total_tokens INTEGER NULL,
          payload_json TEXT NOT NULL,
          usage_json TEXT NULL,
          source_step_id TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(run_id) REFERENCES runs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_agent_context_entries_context
          ON agent_context_entries(context_id, sequence);

        CREATE INDEX IF NOT EXISTS idx_agent_context_entries_final_marker
          ON agent_context_entries(context_id, entry_type, message_type, total_tokens, sequence);

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
        payload=agent_context_payload_from_dict(
            entry_type=entry_type,
            value=_clone(raw_payload),
        ),
        usage=usage,
        source_step_id=str(row["source_step_id"]),
        created_at=str(row["created_at"]),
    )


def _list_entries(
    conn: sqlite3.Connection,
    *,
    context_id: str,
) -> list[AgentContextEntry]:
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


def _list_entries_from_sequence(
    conn: sqlite3.Connection,
    *,
    context_id: str,
    sequence: int,
) -> list[AgentContextEntry]:
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


def _current_total_tokens(
    conn: sqlite3.Connection,
    *,
    context_id: str,
) -> int | None:
    row = conn.execute(
        """
        SELECT total_tokens
        FROM agent_context_entries
        WHERE context_id = ?
          AND entry_type = ?
          AND message_type = ?
          AND total_tokens IS NOT NULL
        ORDER BY sequence DESC
        LIMIT 1
        """,
        (
            context_id,
            AgentContextEntryType.ASSISTANT_MESSAGE.value,
            "final",
        ),
    ).fetchone()
    if row is None:
        return None
    return int(row["total_tokens"])


def _window_marker_sequence(
    conn: sqlite3.Connection,
    *,
    context_id: str,
    cutoff: int,
) -> int | None:
    row = conn.execute(
        """
        SELECT sequence
        FROM agent_context_entries
        WHERE context_id = ?
          AND entry_type = ?
          AND message_type = ?
          AND total_tokens > ?
        ORDER BY sequence ASC
        LIMIT 1
        """,
        (
            context_id,
            AgentContextEntryType.ASSISTANT_MESSAGE.value,
            "final",
            cutoff,
        ),
    ).fetchone()
    if row is None:
        return None
    return int(row["sequence"])


def _last_final_usage(
    conn: sqlite3.Connection,
    *,
    context_id: str,
) -> LLMUsage | None:
    row = conn.execute(
        """
        SELECT usage_json
        FROM agent_context_entries
        WHERE context_id = ?
          AND entry_type = ?
          AND message_type = ?
          AND usage_json IS NOT NULL
        ORDER BY sequence DESC
        LIMIT 1
        """,
        (
            context_id,
            AgentContextEntryType.ASSISTANT_MESSAGE.value,
            "final",
        ),
    ).fetchone()
    if row is None:
        return None
    return _usage_from_json(row["usage_json"])


def _empty_usage() -> LLMUsage:
    return LLMUsage(
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )


def _usage_to_dict(usage: LLMUsage) -> dict[str, int | str | None]:
    result: dict[str, int | str | None] = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }
    if usage.provider is not None:
        result["provider"] = usage.provider
    if usage.model is not None:
        result["model"] = usage.model
    return result


def _message_type(payload: AgentContextPayload) -> str | None:
    if isinstance(payload, AgentAssistantMessagePayload):
        return payload.message_type
    return None


def _total_tokens(payload: AgentContextPayload) -> int | None:
    if isinstance(payload, AgentAssistantMessagePayload):
        return payload.total_tokens
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


def _calculate_entry_stats(entries: list[AgentContextEntry]) -> AgentContextEntryStats:
    user_messages = 0
    assistant_messages = 0
    tool_calls = 0
    tool_results = 0

    for entry in entries:
        if entry.entry_type == AgentContextEntryType.USER_MESSAGE:
            user_messages += 1
            continue
        if entry.entry_type == AgentContextEntryType.ASSISTANT_MESSAGE:
            assistant_messages += 1
            continue
        if entry.entry_type == AgentContextEntryType.TOOL_CALL:
            tool_calls += 1
            continue
        if entry.entry_type == AgentContextEntryType.TOOL_RESULT:
            tool_results += 1

    return AgentContextEntryStats(
        total=len(entries),
        user_messages=user_messages,
        assistant_messages=assistant_messages,
        tool_calls=tool_calls,
        tool_results=tool_results,
    )


def _calculate_usage_stats(entries: list[AgentContextEntry]) -> AgentContextUsageStats:
    usage = _last_final_usage_from_entries(entries)
    if usage is None:
        return AgentContextUsageStats(
            entries=0,
            total_prompt_tokens=0,
            total_response_tokens=0,
            total_tokens=0,
        )

    return AgentContextUsageStats(
        entries=1,
        total_prompt_tokens=usage.prompt_tokens or 0,
        total_response_tokens=usage.completion_tokens or 0,
        total_tokens=usage.total_tokens or 0,
    )


def _last_final_usage_from_entries(entries: list[AgentContextEntry]) -> LLMUsage | None:
    for entry in reversed(entries):
        if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
            continue
        if not isinstance(entry.payload, AgentAssistantMessagePayload):
            continue
        if entry.payload.message_type != "final":
            continue
        return entry.usage
    return None


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


def _clone(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value
