from skiller.domain.agent.context.model import AgentContextState
from skiller.infrastructure.db.datasource.sqlite_connection_source import SqliteConnectionSource


class SqliteAgentContextStateDatasource(SqliteConnectionSource):
    def get_state(self, *, context_id: str) -> AgentContextState | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT context_id,
                       start_sequence,
                       compacted_sequence,
                       compaction_id
                FROM agent_context_state
                WHERE context_id = ?
                """,
                (context_id,),
            ).fetchone()
        if row is None:
            return None
        compacted_sequence = row["compacted_sequence"]
        return AgentContextState(
            context_id=str(row["context_id"]),
            start_sequence=int(row["start_sequence"]),
            compacted_sequence=(
                int(compacted_sequence) if compacted_sequence is not None else None
            ),
            compaction_id=int(row["compaction_id"]),
        )

    def save_state(self, *, state: AgentContextState) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_context_state (
                  context_id,
                  start_sequence,
                  compacted_sequence,
                  compaction_id
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(context_id) DO UPDATE SET
                  start_sequence = excluded.start_sequence,
                  compacted_sequence = excluded.compacted_sequence,
                  compaction_id = excluded.compaction_id,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (
                    state.context_id,
                    state.start_sequence,
                    state.compacted_sequence,
                    state.compaction_id,
                ),
            )
