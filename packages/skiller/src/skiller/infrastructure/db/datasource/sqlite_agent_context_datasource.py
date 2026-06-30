import json
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any

from skiller.domain.agent.context.compact_delta import legacy_compact_delta_tokens
from skiller.domain.agent.context.model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextPayload,
    AgentContextUsageMarker,
    agent_context_payload_from_dict,
    agent_context_payload_to_dict,
)
from skiller.domain.agent.context.stats_model import (
    AgentContextObservedStats,
    AgentContextObservedWindowStats,
)
from skiller.domain.agent.llm.model import LLMUsage
from skiller.infrastructure.db.datasource.sqlite_connection_source import SqliteConnectionSource


class SqliteAgentContextDatasource(SqliteConnectionSource):
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
        delta_compact_tokens: int | None = None,
        window_base: bool | None = None,
        source_step_id: str,
    ) -> AgentContextEntry:
        with self._connect() as conn:
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
                  delta_compact_tokens,
                  window_base,
                  payload_json,
                  usage_json,
                  source_step_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    delta_compact_tokens,
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
            return self._list_entries(conn, context_id=context_id)

    def list_entries_from_sequence(
        self,
        *,
        context_id: str,
        start_sequence: int,
    ) -> list[AgentContextEntry]:
        with self._connect() as conn:
            return self._list_entries_from_sequence(
                conn,
                context_id=context_id,
                start_sequence=start_sequence,
            )

    def list_window_entries(
        self,
        *,
        context_id: str,
        window_width_tokens: int,
    ) -> list[AgentContextEntry]:
        with self._connect() as conn:
            start_sequence = self.window_start_sequence(
                conn,
                context_id=context_id,
                window_width_tokens=window_width_tokens,
            )
            if start_sequence == 0:
                return []
            rows = conn.execute(
                """
                SELECT *
                FROM agent_context_entries
                WHERE context_id = ?
                  AND sequence >= ?
                ORDER BY sequence ASC
                """,
                (context_id, start_sequence),
            ).fetchall()
        return [_build_entry(row) for row in rows]

    def list_compact_entries(
        self,
        *,
        context_id: str,
        window_width_tokens: int,
        keep_last_markers: int,
    ) -> list[AgentContextEntry]:
        keep_last_markers = min(100, max(1, keep_last_markers))
        with self._connect() as conn:
            self._backfill_compact_delta_tokens(conn, context_id=context_id)
            protected_window = self._protected_compact_window(
                conn,
                context_id=context_id,
                keep_last_markers=keep_last_markers,
            )
            if protected_window is None:
                return self._list_entries(conn, context_id=context_id)
            if protected_window.tokens >= window_width_tokens:
                start_sequence = self.window_start_sequence(
                    conn,
                    context_id=context_id,
                    window_width_tokens=window_width_tokens,
                )
                return self._list_entries_from_sequence(
                    conn,
                    context_id=context_id,
                    start_sequence=start_sequence,
                )

            compact_start_sequence = self._compact_start_sequence(
                conn,
                context_id=context_id,
                before_sequence=protected_window.start_sequence,
                window_width_tokens=window_width_tokens - protected_window.tokens,
            )
            return self._list_compact_entries(
                conn,
                context_id=context_id,
                compact_start_sequence=compact_start_sequence,
                protected_start_sequence=protected_window.start_sequence,
            )

    def get_last_usage_marker(
        self,
        *,
        context_id: str,
    ) -> AgentContextUsageMarker | None:
        with self._connect() as conn:
            return self._last_usage_marker(conn, context_id=context_id)

    def estimate_window_tokens(
        self,
        *,
        context_id: str,
        start_sequence: int,
    ) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(
                  SUM(CASE WHEN delta_tokens > 0 THEN delta_tokens ELSE 0 END),
                  0
                ) AS estimated_tokens
                FROM agent_context_entries
                WHERE context_id = ?
                  AND sequence >= ?
                """,
                (context_id, start_sequence),
            ).fetchone()
        if row is None:
            return 0
        return int(row["estimated_tokens"])

    def get_observed_stats(
        self,
        *,
        context_id: str,
    ) -> AgentContextObservedStats:
        with self._connect() as conn:
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
            current_tokens = marker.prompt_tokens if marker is not None else 0

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

    def _list_entries(
        self,
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
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
        start_sequence: int,
    ) -> list[AgentContextEntry]:
        if start_sequence == 0:
            return []
        rows = conn.execute(
            """
            SELECT *
            FROM agent_context_entries
            WHERE context_id = ?
              AND sequence >= ?
            ORDER BY sequence ASC
            """,
            (context_id, start_sequence),
        ).fetchall()
        return [_build_entry(row) for row in rows]

    def _backfill_compact_delta_tokens(
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
    ) -> None:
        rows = conn.execute(
            """
            SELECT *
            FROM agent_context_entries
            WHERE context_id = ?
              AND usage_json IS NOT NULL
              AND delta_tokens IS NOT NULL
              AND (
                delta_compact_tokens IS NULL
                OR (delta_tokens > 0 AND delta_compact_tokens = 0)
              )
            ORDER BY sequence ASC
            """,
            (context_id,),
        ).fetchall()
        for row in rows:
            entry = _build_entry(row)
            delta_compact_tokens = legacy_compact_delta_tokens(
                delta_tokens=entry.delta_tokens or 0,
            )
            conn.execute(
                """
                UPDATE agent_context_entries
                SET delta_compact_tokens = ?
                WHERE id = ?
                """,
                (delta_compact_tokens, entry.id),
            )

    def _protected_compact_window(
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
        keep_last_markers: int,
    ) -> "_ProtectedCompactWindow | None":
        marker_row = conn.execute(
            """
            SELECT sequence
            FROM agent_context_entries
            WHERE context_id = ?
              AND usage_json IS NOT NULL
              AND delta_tokens IS NOT NULL
            ORDER BY sequence DESC
            LIMIT 1 OFFSET ?
            """,
            (context_id, keep_last_markers - 1),
        ).fetchone()
        if marker_row is None:
            marker_row = conn.execute(
                """
                SELECT MIN(sequence) AS sequence
                FROM agent_context_entries
                WHERE context_id = ?
                  AND usage_json IS NOT NULL
                  AND delta_tokens IS NOT NULL
                """,
                (context_id,),
            ).fetchone()
        if marker_row is None or marker_row["sequence"] is None:
            return None

        marker_sequence = int(marker_row["sequence"])
        start_sequence = self._usage_marker_block_start_sequence(
            conn,
            context_id=context_id,
            marker_sequence=marker_sequence,
        )
        tokens = self._sum_delta_tokens_from_marker(
            conn,
            context_id=context_id,
            marker_sequence=start_sequence,
        )
        return _ProtectedCompactWindow(
            start_sequence=start_sequence,
            tokens=tokens,
        )

    def _compact_start_sequence(
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
        before_sequence: int,
        window_width_tokens: int,
    ) -> int:
        row = conn.execute(
            """
            WITH usage_rows AS (
              SELECT sequence,
                     CASE
                       WHEN delta_compact_tokens > 0 THEN delta_compact_tokens
                       ELSE 0
                     END AS delta_tokens
              FROM agent_context_entries
              WHERE context_id = ?
                AND usage_json IS NOT NULL
                AND sequence < ?
            ),
            running AS (
              SELECT sequence,
                     SUM(delta_tokens) OVER (
                       ORDER BY sequence DESC
                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                     ) AS running_tokens
              FROM usage_rows
            ),
            selected_usage AS (
              SELECT MIN(sequence) AS sequence
              FROM running
              WHERE running_tokens <= ?
            ),
            fallback_usage AS (
              SELECT MAX(sequence) AS sequence
              FROM usage_rows
            )
            SELECT COALESCE(selected_usage.sequence, fallback_usage.sequence, 0)
              AS marker_sequence
            FROM selected_usage, fallback_usage
            """,
            (context_id, before_sequence, window_width_tokens),
        ).fetchone()
        if row is None or row["marker_sequence"] is None:
            return 0
        marker_sequence = int(row["marker_sequence"])
        if marker_sequence == 0:
            return 0
        return self._usage_marker_block_start_sequence(
            conn,
            context_id=context_id,
            marker_sequence=marker_sequence,
        )

    def _list_compact_entries(
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
        compact_start_sequence: int,
        protected_start_sequence: int,
    ) -> list[AgentContextEntry]:
        rows = conn.execute(
            """
            SELECT *
            FROM agent_context_entries
            WHERE context_id = ?
              AND sequence >= ?
              AND (
                sequence >= ?
                OR NOT (
                  entry_type IN (?, ?)
                  OR (
                    entry_type = ?
                    AND message_type = ?
                  )
                )
              )
            ORDER BY sequence ASC
            """,
            (
                context_id,
                compact_start_sequence,
                protected_start_sequence,
                AgentContextEntryType.TOOL_CALL.value,
                AgentContextEntryType.TOOL_RESULT.value,
                AgentContextEntryType.ASSISTANT_MESSAGE.value,
                AgentAssistantMessageType.TOOL_CALLS.value,
            ),
        ).fetchall()
        return [_build_entry(row) for row in rows]

    def _usage_marker_block_start_sequence(
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
        marker_sequence: int,
    ) -> int:
        row = conn.execute(
            """
            SELECT MAX(sequence) AS sequence
            FROM agent_context_entries
            WHERE context_id = ?
              AND usage_json IS NOT NULL
              AND sequence < ?
            """,
            (context_id, marker_sequence),
        ).fetchone()
        if row is not None and row["sequence"] is not None:
            return int(row["sequence"])
        row = conn.execute(
            """
            SELECT MIN(sequence) AS sequence
            FROM agent_context_entries
            WHERE context_id = ?
            """,
            (context_id,),
        ).fetchone()
        if row is None or row["sequence"] is None:
            return marker_sequence
        return int(row["sequence"])

    def _sum_delta_tokens_from_marker(
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
        marker_sequence: int,
    ) -> int:
        row = conn.execute(
            """
            SELECT COALESCE(
              SUM(CASE WHEN delta_tokens > 0 THEN delta_tokens ELSE 0 END),
              0
            ) AS tokens
            FROM agent_context_entries
            WHERE context_id = ?
              AND usage_json IS NOT NULL
              AND sequence >= ?
            """,
            (context_id, marker_sequence),
        ).fetchone()
        if row is None:
            return 0
        return int(row["tokens"])

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

    def window_start_sequence(
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
        window_width_tokens: int,
    ) -> int:
        row = conn.execute(
            """
            WITH usage_rows AS (
              SELECT sequence,
                     CASE
                       WHEN delta_tokens > 0 THEN delta_tokens
                       ELSE 0
                     END AS delta_tokens
              FROM agent_context_entries
              WHERE context_id = ?
                AND usage_json IS NOT NULL
            ),
            first_entry AS (
              SELECT MIN(sequence) AS sequence
              FROM agent_context_entries
              WHERE context_id = ?
            ),
            running AS (
              SELECT sequence,
                     SUM(delta_tokens) OVER (
                       ORDER BY sequence DESC
                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                     ) AS running_tokens
              FROM usage_rows
            ),
            selected_usage AS (
              SELECT MIN(sequence) AS sequence
              FROM running
              WHERE running_tokens <= ?
            ),
            fallback_usage AS (
              SELECT MAX(sequence) AS sequence
              FROM usage_rows
            ),
            previous_usage AS (
              SELECT MAX(usage_rows.sequence) AS sequence
              FROM usage_rows, selected_usage
              WHERE selected_usage.sequence IS NOT NULL
                AND usage_rows.sequence < selected_usage.sequence
            )
            SELECT COALESCE(
              CASE
                WHEN selected_usage.sequence IS NULL THEN fallback_usage.sequence
                ELSE (
                  SELECT MIN(sequence)
                  FROM agent_context_entries
                  WHERE context_id = ?
                    AND sequence > COALESCE(previous_usage.sequence, 0)
                )
              END,
              first_entry.sequence,
              0
            ) AS start_sequence
            FROM selected_usage, fallback_usage, previous_usage, first_entry
            """,
            (context_id, context_id, window_width_tokens, context_id),
        ).fetchone()
        if row is None:
            return 0
        return int(row["start_sequence"])


@dataclass(frozen=True)
class _ProtectedCompactWindow:
    start_sequence: int
    tokens: int


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
        delta_compact_tokens=_optional_int(row["delta_compact_tokens"]),
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
        result["model"] = usage.model
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


def _optional_model(value: object) -> str | None:
    value = _optional_string(value)
    if value is None:
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
