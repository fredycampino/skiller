from skiller.domain.run.run_model import RunAgent
from skiller.infrastructure.db.datasource.sqlite_connection_source import SqliteConnectionSource
from skiller.infrastructure.db.sqlite_run_agent_mapper import (
    agents_from_json,
    agents_to_json,
)


class SqliteRunAgentDatasource(SqliteConnectionSource):
    def _get_agents(self, *, run_id: str) -> dict[str, RunAgent]:
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
            return {}
        return agents_from_json(row["agents_json"])

    def get_agent(
        self,
        *,
        run_id: str,
        agent_id: str,
    ) -> RunAgent | None:
        agents = self._get_agents(run_id=run_id)
        return agents.get(agent_id)

    def get_first_agent(self, *, run_id: str) -> RunAgent | None:
        agents = self._get_agents(run_id=run_id)
        return next(iter(agents.values()), None)

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
            agents[agent_id] = RunAgent(
                agent_id=agent_id,
                context_id=context_id,
            )
            conn.execute(
                """
                UPDATE runs
                SET agents_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (agents_to_json(agents), run_id),
            )
