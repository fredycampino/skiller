import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
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
from skiller.domain.agent.agent_run_scope import AgentRunScope
from skiller.domain.agent.agent_stats_model import (
    AgentContextEntryStats,
    AgentContextStats,
    AgentContextUsageStats,
)
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult
from skiller.infrastructure.db.sqlite_repository import SqliteRepository


@dataclass(frozen=True)
class _AgentUsage:
    run_id: str
    context_id: str
    usage: LLMUsage


class SqliteAgentContextStore(
    SqliteRepository,
    AgentContextStorePort,
    AgentContextStatsPort,
):
    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)
        self._usage: _AgentUsage | None = None

    def init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            ensure_agent_context_schema(conn)

    def append_user_message(
        self,
        *,
        scope: AgentRunScope,
        text: str,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=scope.run_id,
            context_id=scope.context_id,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload=AgentUserMessagePayload(text=text),
            source_step_id=scope.agent_id,
        )

    def append_assistant_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        message_type: str,
        text: str,
        usage: LLMUsage | None = None,
    ) -> AgentContextEntry:
        current_usage = self.get_usage(scope=scope)
        next_usage = _add_usage(current_usage, usage) if usage is not None else current_usage
        entry = self._append_entry(
            run_id=scope.run_id,
            context_id=scope.context_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload=AgentAssistantMessagePayload(
                turn_id=turn_id,
                message_type=message_type,
                text=text,
                total_tokens=next_usage.total_tokens,
            ),
            usage=usage,
            source_step_id=scope.agent_id,
        )
        self._usage = _AgentUsage(
            run_id=scope.run_id,
            context_id=scope.context_id,
            usage=next_usage,
        )
        return entry

    def append_tool_call(
        self,
        *,
        scope: AgentRunScope,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=scope.run_id,
            context_id=scope.context_id,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload=AgentToolCallPayload(
                turn_id=tool_call.turn_id,
                parent_sequence=tool_call.parent_sequence,
                tool_call_id=tool_call.tool_call_id,
                tool=tool_call.tool,
                args=tool_call.args,
            ),
            source_step_id=scope.agent_id,
        )

    def append_tool_result(
        self,
        *,
        scope: AgentRunScope,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry:
        result = tool_result.result
        return self._append_entry(
            run_id=scope.run_id,
            context_id=scope.context_id,
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
            source_step_id=scope.agent_id,
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
                  usage_json,
                  source_step_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    run_id,
                    context_id,
                    sequence,
                    entry_type.value,
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

    def list_entries(self, *, scope: AgentRunScope) -> list[AgentContextEntry]:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            rows = conn.execute(
                """
                SELECT *
                FROM agent_context_entries
                WHERE run_id = ? AND context_id = ?
                ORDER BY sequence ASC
                """,
                (scope.run_id, scope.context_id),
            ).fetchall()
        return [_build_entry(row) for row in rows]

    def get_stats(self, *, scope: AgentRunScope) -> AgentContextStats:
        entries = self.list_entries(scope=scope)
        return AgentContextStats(
            entries=_calculate_entry_stats(entries),
            usage=_calculate_usage_stats(entries),
        )

    def get_usage(self, *, scope: AgentRunScope) -> LLMUsage:
        if (
            self._usage is not None
            and self._usage.run_id == scope.run_id
            and self._usage.context_id == scope.context_id
        ):
            return self._usage.usage

        stats = self.get_stats(scope=scope)
        usage = LLMUsage(
            prompt_tokens=stats.usage.total_prompt_tokens,
            completion_tokens=stats.usage.total_response_tokens,
            total_tokens=stats.usage.total_tokens,
        )
        self._usage = _AgentUsage(
            run_id=scope.run_id,
            context_id=scope.context_id,
            usage=usage,
        )
        return usage

    def next_turn_id(self, *, scope: AgentRunScope) -> str:
        with self._connect() as conn:
            ensure_agent_context_schema(conn)
            row = conn.execute(
                """
                SELECT COUNT(*) AS turn_entries
                FROM agent_context_entries
                WHERE run_id = ?
                  AND context_id = ?
                  AND entry_type IN (?, ?)
                """,
                (
                    scope.run_id,
                    scope.context_id,
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
          usage_json TEXT NULL,
          source_step_id TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(run_id) REFERENCES runs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_agent_context_entries_context
          ON agent_context_entries(run_id, context_id, sequence);

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


def _usage_to_dict(usage: LLMUsage) -> dict[str, int | None]:
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }


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
    usage_entries = 0
    total_prompt_tokens = 0
    total_response_tokens = 0
    total_tokens = 0

    for entry in entries:
        usage = entry.usage
        if usage is None:
            continue
        usage_entries += 1
        total_prompt_tokens += usage.prompt_tokens or 0
        total_response_tokens += usage.completion_tokens or 0
        total_tokens += usage.total_tokens or 0

    return AgentContextUsageStats(
        entries=usage_entries,
        total_prompt_tokens=total_prompt_tokens,
        total_response_tokens=total_response_tokens,
        total_tokens=total_tokens,
    )


def _add_usage(current: LLMUsage, entry_usage: LLMUsage) -> LLMUsage:
    return LLMUsage(
        prompt_tokens=(current.prompt_tokens or 0) + (entry_usage.prompt_tokens or 0),
        completion_tokens=(current.completion_tokens or 0)
        + (entry_usage.completion_tokens or 0),
        total_tokens=(current.total_tokens or 0) + (entry_usage.total_tokens or 0),
    )


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _clone(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value
