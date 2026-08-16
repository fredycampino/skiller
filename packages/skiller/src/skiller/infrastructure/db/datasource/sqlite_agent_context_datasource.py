import json
import sqlite3
import uuid
from typing import Any

from skiller.domain.agent.context.model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextCompactDeltaUpdate,
    AgentContextCompactionQuery,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextPayload,
    AgentContextState,
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


class SqliteAgentContextDatasource(SqliteConnectionSource):
    def append_entry(
        self,
        *,
        run_id: str,
        context_id: str,
        entry_type: AgentContextEntryType,
        payload: AgentContextPayload,
        usage: LLMUsage | None = None,
        delta_tokens: int | None = None,
        delta_compact_tokens: int | None = None,
        compaction_id: int | None = None,
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
                  delta_tokens,
                  delta_compact_tokens,
                  compaction_id,
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
                    delta_tokens,
                    delta_compact_tokens,
                    compaction_id,
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

    def list_raw_entries(
        self,
        *,
        context_id: str,
        start_sequence: int,
    ) -> AgentContextWindowEntries:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT agent_context_entries.*,
                       SUM(
                         CASE
                           WHEN usage_json IS NOT NULL
                            AND json_extract(usage_json, '$.prompt_tokens') IS NOT NULL
                            AND delta_tokens > 0 THEN delta_tokens
                           ELSE 0
                         END
                       ) OVER () AS selected_tokens
                FROM agent_context_entries
                WHERE context_id = ?
                  AND sequence >= ?
                ORDER BY sequence ASC
                """,
                (context_id, start_sequence),
            ).fetchall()
        if not rows:
            return AgentContextWindowEntries(entries=[], estimated_tokens=0)
        return AgentContextWindowEntries(
            entries=[_build_entry(row) for row in rows],
            estimated_tokens=int(rows[0]["selected_tokens"]),
        )

    def list_compact_entries(
        self,
        *,
        context_id: str,
        start_sequence: int,
        compacted_sequence: int,
    ) -> AgentContextWindowEntries:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT agent_context_entries.*,
                       SUM(
                         CASE
                           WHEN delta_compact_tokens > 0 THEN delta_compact_tokens
                           ELSE 0
                         END
                       ) OVER () AS selected_tokens
                FROM agent_context_entries
                WHERE context_id = ?
                  AND sequence BETWEEN ? AND ?
                  AND NOT (
                    entry_type IN (?, ?)
                    OR (
                      entry_type = ?
                      AND message_type = ?
                    )
                  )
                ORDER BY sequence ASC
                """,
                (
                    context_id,
                    start_sequence,
                    compacted_sequence,
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

    def select_compaction_state(
        self,
        *,
        query: AgentContextCompactionQuery,
    ) -> AgentContextState:
        raw_boundary = query.compacted_sequence
        if raw_boundary is None:
            raw_boundary = query.start_sequence - 1

        with self._connect() as conn:
            row = conn.execute(
                """
                WITH source_entries AS (
                  SELECT sequence,
                         delta_compact_tokens,
                         CASE
                           WHEN usage_json IS NOT NULL
                            AND json_extract(usage_json, '$.prompt_tokens') IS NOT NULL
                            AND delta_tokens IS NOT NULL THEN 1
                           ELSE 0
                         END AS is_marker,
                         CASE
                           WHEN delta_tokens > 0 THEN delta_tokens
                           ELSE 0
                         END AS raw_tokens
                  FROM agent_context_entries
                  WHERE context_id = ?
                    AND sequence >= ?
                ),
                tagged_entries AS (
                  SELECT sequence,
                         delta_compact_tokens,
                         is_marker,
                         raw_tokens,
                         COALESCE(
                           SUM(is_marker) OVER (
                             ORDER BY sequence ASC
                             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                           ),
                           0
                         ) AS block_id
                  FROM source_entries
                ),
                complete_blocks AS (
                  SELECT block_id,
                         MIN(sequence) AS block_start_sequence,
                         MAX(CASE WHEN is_marker = 1 THEN sequence END) AS marker_sequence,
                         MAX(CASE WHEN is_marker = 1 THEN raw_tokens ELSE 0 END) AS raw_tokens,
                         SUM(
                           CASE
                             WHEN delta_compact_tokens > 0 THEN delta_compact_tokens
                             ELSE 0
                           END
                         ) AS compact_tokens
                  FROM tagged_entries
                  GROUP BY block_id
                  HAVING SUM(is_marker) > 0
                ),
                raw_blocks AS (
                  SELECT block_start_sequence,
                         marker_sequence,
                         raw_tokens,
                         ROW_NUMBER() OVER (
                           ORDER BY marker_sequence DESC
                         ) AS blocks_from_tail,
                         SUM(raw_tokens) OVER (
                           ORDER BY marker_sequence DESC
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                         ) AS running_tokens
                  FROM complete_blocks
                  WHERE marker_sequence > ?
                ),
                selected_raw_marker AS (
                  SELECT COALESCE(
                    (
                      SELECT MIN(marker_sequence)
                      FROM raw_blocks
                      WHERE blocks_from_tail <= ?
                        AND running_tokens <= ?
                    ),
                    (SELECT MAX(marker_sequence) FROM raw_blocks)
                  ) AS marker_sequence
                ),
                selected_raw AS (
                  SELECT raw_blocks.block_start_sequence,
                         raw_blocks.running_tokens
                  FROM raw_blocks
                  JOIN selected_raw_marker
                    ON selected_raw_marker.marker_sequence = raw_blocks.marker_sequence
                ),
                boundary AS (
                  SELECT block_start_sequence - 1 AS compacted_sequence,
                         CASE
                           WHEN running_tokens < ? THEN ? - running_tokens
                           ELSE 0
                         END AS remaining_tokens
                  FROM selected_raw
                ),
                compact_blocks AS (
                  SELECT complete_blocks.block_start_sequence,
                         complete_blocks.marker_sequence,
                         SUM(complete_blocks.compact_tokens) OVER (
                           ORDER BY complete_blocks.marker_sequence DESC
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                         ) AS running_tokens
                  FROM complete_blocks
                  JOIN boundary
                    ON complete_blocks.marker_sequence <= boundary.compacted_sequence
                ),
                selected_compact AS (
                  SELECT compact_blocks.block_start_sequence
                  FROM compact_blocks
                  JOIN boundary ON 1 = 1
                  WHERE boundary.remaining_tokens > 0
                    AND compact_blocks.running_tokens <= boundary.remaining_tokens
                  ORDER BY compact_blocks.marker_sequence ASC
                  LIMIT 1
                )
                SELECT COALESCE(
                         (SELECT block_start_sequence FROM selected_compact),
                         boundary.compacted_sequence + 1
                       ) AS start_sequence,
                       boundary.compacted_sequence
                FROM boundary
                """,
                (
                    query.context_id,
                    query.start_sequence,
                    raw_boundary,
                    query.keep_last_blocks,
                    query.target_tokens,
                    query.target_tokens,
                    query.target_tokens,
                ),
            ).fetchone()
        if row is None:
            raise ValueError("Agent context has no complete raw block to compact")
        return AgentContextState(
            context_id=query.context_id,
            start_sequence=int(row["start_sequence"]),
            compacted_sequence=int(row["compacted_sequence"]),
            compaction_id=query.compaction_id + 1,
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

            state = conn.execute(
                """
                SELECT start_sequence
                FROM agent_context_state
                WHERE context_id = ?
                """,
                (context_id,),
            ).fetchone()
            marker = self._last_usage_marker(conn, context_id=context_id)
            state_start_sequence = (
                int(state["start_sequence"]) if state is not None else int(totals["start_sequence"])
            )
            current_tokens = marker.prompt_tokens if marker is not None else 0

        return AgentContextObservedStats(
            entries=int(totals["entries"]),
            estimated_tokens=int(totals["estimated_tokens"]),
            window=AgentContextObservedWindowStats(
                start_sequence=state_start_sequence,
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
                   compaction_id
            FROM agent_context_entries
            WHERE context_id = ?
              AND usage_json IS NOT NULL
              AND delta_tokens IS NOT NULL
              AND compaction_id IS NOT NULL
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
                compaction_id=int(row["compaction_id"]),
            )
        return None


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
        delta_tokens=_optional_int(row["delta_tokens"]),
        delta_compact_tokens=_optional_int(row["delta_compact_tokens"]),
        compaction_id=_optional_int(row["compaction_id"]),
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
        "estimated_system_tokens": usage.estimated_system_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
    }
    if usage.provider is not None:
        result["provider"] = usage.provider
    if usage.model is not None:
        result["model"] = usage.model
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
        estimated_system_tokens=_optional_int(parsed.get("estimated_system_tokens")),
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
