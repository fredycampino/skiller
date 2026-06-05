from skiller.domain.run.run_model import RunAgent, RunAgentWindow
from skiller.infrastructure.db.sqlite_repository import SqliteRepository
from skiller.infrastructure.db.sqlite_run_agent_mapper import (
    agents_from_json,
    agents_to_json,
)


class SqliteRunAgentDatasource(SqliteRepository):
    def get_agent(
        self,
        *,
        run_id: str,
        agent_id: str,
    ) -> RunAgent | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT agents_json
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        agents = agents_from_json(row["agents_json"])
        return agents.get(agent_id)

    def attach_agent(
        self,
        *,
        run_id: str,
        agent_id: str,
        context_id: str,
    ) -> None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT agents_json
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                return

            agents = agents_from_json(row["agents_json"])
            current_agent = agents.get(agent_id)
            agents[agent_id] = RunAgent(
                agent_id=agent_id,
                context_id=context_id,
                window_start_sequence=(
                    current_agent.window_start_sequence
                    if current_agent is not None
                    else 0
                ),
                window_base=(
                    current_agent.window_base
                    if current_agent is not None
                    else True
                ),
            )
            conn.execute(
                """
                UPDATE runs
                SET agents_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (agents_to_json(agents), run_id),
            )

    def update_agent_window(
        self,
        *,
        run_id: str,
        window: RunAgentWindow,
    ) -> None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT agents_json
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                return

            agents = agents_from_json(row["agents_json"])
            current_agent = agents.get(window.agent_id)
            agents[window.agent_id] = RunAgent(
                agent_id=window.agent_id,
                context_id=(
                    current_agent.context_id
                    if current_agent is not None
                    else None
                ),
                window_start_sequence=window.window_start_sequence,
                window_base=window.window_base,
            )
            conn.execute(
                """
                UPDATE runs
                SET agents_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (agents_to_json(agents), run_id),
            )
