import json
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any

from skiller.domain.agent.context.model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextCompactDeltaUpdate,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextPayload,
    AgentContextUsageMarker,
    AgentContextWindowEntries,
    agent_context_payload_from_dict,
    agent_context_payload_to_dict,
)
from skiller.domain.agent.context.stats_model import (
    AgentContextObservedStats,
    AgentContextObservedWindowStats,
)
from skiller.domain.agent.llm.model import LLMUsage
from skiller.infrastructure.db.datasource.sqlite_connection_source import SqliteConnectionSource


@dataclass(frozen=True)
class AgentContextProtectedEntries:
    entries: list[AgentContextEntry]
    tokens: int


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
    ) -> AgentContextWindowEntries:
        with self._connect() as conn:
            start_sequence = self.window_start_sequence(
                conn,
                context_id=context_id,
                window_width_tokens=window_width_tokens,
            )
            if start_sequence == 0:
                return AgentContextWindowEntries(entries=[], estimated_tokens=0)
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
            estimated_tokens = self._estimate_window_tokens(
                conn,
                context_id=context_id,
                start_sequence=start_sequence,
            )
        return AgentContextWindowEntries(
            entries=[_build_entry(row) for row in rows],
            estimated_tokens=estimated_tokens,
        )

    def list_protected_entries(
        self,
        *,
        context_id: str,
        window_width_tokens: int,
        keep_last_blocks: int,
    ) -> AgentContextProtectedEntries:
        with self._connect() as conn:
            rows = conn.execute(
                """
                WITH usage_blocks AS (
                  SELECT sequence AS marker_sequence,
                         COALESCE(
                           LAG(sequence) OVER (ORDER BY sequence ASC),
                           0
                         ) AS previous_marker_sequence,
                         CASE
                           WHEN delta_tokens > 0 THEN delta_tokens
                           ELSE 0
                         END AS block_tokens
                  FROM agent_context_entries
                  WHERE context_id = ?
                    AND usage_json IS NOT NULL
                    AND delta_tokens IS NOT NULL
                ),
                running AS (
                  SELECT marker_sequence,
                         previous_marker_sequence,
                         ROW_NUMBER() OVER (
                           ORDER BY marker_sequence DESC
                         ) AS blocks_from_tail,
                         SUM(block_tokens) OVER (
                           ORDER BY marker_sequence DESC
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                         ) AS running_tokens
                  FROM usage_blocks
                ),
                selected_block AS (
                  SELECT MIN(marker_sequence) AS marker_sequence
                  FROM running
                  WHERE blocks_from_tail <= ?
                    AND running_tokens <= ?
                ),
                latest_block AS (
                  SELECT MAX(marker_sequence) AS marker_sequence
                  FROM running
                ),
                protected_start AS (
                  SELECT r.previous_marker_sequence + 1 AS sequence,
                         r.running_tokens AS tokens
                  FROM running r
                  WHERE r.marker_sequence = COALESCE(
                    (SELECT marker_sequence FROM selected_block),
                    (SELECT marker_sequence FROM latest_block)
                  )
                )
                SELECT e.*,
                       protected_start.tokens AS protected_tokens
                FROM agent_context_entries e
                JOIN protected_start ON 1 = 1
                WHERE e.context_id = ?
                  AND e.sequence >= protected_start.sequence
                ORDER BY e.sequence ASC
                """,
                (
                    context_id,
                    keep_last_blocks,
                    window_width_tokens,
                    context_id,
                ),
            ).fetchall()
        if not rows:
            return AgentContextProtectedEntries(entries=[], tokens=0)
        return AgentContextProtectedEntries(
            entries=[_build_entry(row) for row in rows],
            tokens=int(rows[0]["protected_tokens"]),
        )

    def list_compact_entries(
        self,
        *,
        context_id: str,
        start_sequence: int,
        window_width_tokens: int,
    ) -> AgentContextWindowEntries:
        with self._connect() as conn:
            rows = conn.execute(
                """
                WITH compact_markers AS (
                  SELECT sequence,
                         CASE
                           WHEN delta_compact_tokens > 0 THEN delta_compact_tokens
                           ELSE 0
                         END AS compact_tokens
                  FROM agent_context_entries
                  WHERE context_id = ?
                    AND sequence <= ?
                    AND delta_compact_tokens IS NOT NULL
                ),
                running AS (
                  SELECT sequence,
                         SUM(compact_tokens) OVER (
                           ORDER BY sequence DESC
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                         ) AS running_tokens
                  FROM compact_markers
                ),
                selected_range AS (
                  SELECT MIN(sequence) AS start_sequence,
                         MAX(sequence) AS end_sequence,
                         MAX(running_tokens) AS tokens
                  FROM running
                  WHERE running_tokens <= ?
                )
                SELECT e.*,
                       selected_range.tokens AS selected_tokens
                FROM agent_context_entries e
                JOIN selected_range ON 1 = 1
                WHERE e.context_id = ?
                  AND selected_range.start_sequence IS NOT NULL
                  AND e.sequence BETWEEN selected_range.start_sequence
                                     AND selected_range.end_sequence
                  AND NOT (
                    e.entry_type IN (?, ?)
                    OR (
                      e.entry_type = ?
                      AND e.message_type = ?
                    )
                  )
                ORDER BY e.sequence ASC
                """,
                (
                    context_id,
                    start_sequence,
                    window_width_tokens,
                    context_id,
                    AgentContextEntryType.TOOL_CALL.value,
                    AgentContextEntryType.TOOL_RESULT.value,
                    AgentContextEntryType.ASSISTANT_MESSAGE.value,
                    AgentAssistantMessageType.TOOL_CALLS.value,
                ),
            ).fetchall()
        if not rows:
            return AgentContextWindowEntries(entries=[], estimated_tokens=0)
        return AgentContextWindowEntries(
            entries=[_build_entry(row) for row in rows],
            estimated_tokens=int(rows[0]["selected_tokens"]),
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
            return self._estimate_window_tokens(
                conn,
                context_id=context_id,
                start_sequence=start_sequence,
            )

    def _estimate_window_tokens(
        self,
        conn: sqlite3.Connection,
        *,
        context_id: str,
        start_sequence: int,
    ) -> int:
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

    def payload_chars_from_sequence(
        self,
        *,
        context_id: str,
        start_sequence: int,
    ) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(LENGTH(payload_json)), 0) AS payload_chars
                FROM agent_context_entries
                WHERE context_id = ?
                  AND sequence >= ?
                """,
                (context_id, start_sequence),
            ).fetchone()
        if row is None:
            return 0
        return int(row["payload_chars"])

    def compact_delta_block(
        self,
        *,
        context_id: str,
        marker_sequence: int,
    ) -> list[AgentContextEntry]:
        with self._connect() as conn:
            marker_row = conn.execute(
                """
                SELECT sequence
                FROM agent_context_entries
                WHERE context_id = ?
                  AND sequence = ?
                  AND usage_json IS NOT NULL
                  AND delta_tokens IS NOT NULL
                """,
                (context_id, marker_sequence),
            ).fetchone()
            if marker_row is None:
                return []
            row = conn.execute(
                """
                SELECT MAX(sequence) AS previous_marker_sequence
                FROM agent_context_entries
                WHERE context_id = ?
                  AND usage_json IS NOT NULL
                  AND delta_tokens IS NOT NULL
                  AND sequence < ?
                """,
                (context_id, marker_sequence),
            ).fetchone()
            previous_marker_sequence = 0
            if row is not None and row["previous_marker_sequence"] is not None:
                previous_marker_sequence = int(row["previous_marker_sequence"])
            rows = conn.execute(
                """
                SELECT *
                FROM agent_context_entries
                WHERE context_id = ?
                  AND sequence > ?
                  AND sequence <= ?
                ORDER BY sequence ASC
                """,
                (context_id, previous_marker_sequence, marker_sequence),
            ).fetchall()
        return [_build_entry(row) for row in rows]

    def update_compact_delta_tokens(
        self,
        *,
        context_id: str,
        updates: list[AgentContextCompactDeltaUpdate],
    ) -> None:
        if not updates:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                UPDATE agent_context_entries
                SET delta_compact_tokens = ?
                WHERE context_id = ?
                  AND sequence = ?
                """,
                [(update.delta_compact_tokens, context_id, update.sequence) for update in updates],
            )

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
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
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
        output_tokens=_optional_int(parsed.get("output_tokens")),
        total_tokens=_optional_int(parsed.get("total_tokens")),
        cache_read_tokens=_optional_int(parsed.get("cache_read_tokens")),
        cache_write_tokens=_optional_int(parsed.get("cache_write_tokens")),
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
