from skiller.domain.run.run_agent_store_port import RunAgentStorePort
from skiller.domain.run.run_model import RunAgent
from skiller.infrastructure.db.datasource.sqlite_run_agent_datasource import (
    SqliteRunAgentDatasource,
)


class SqliteRunAgentStore(RunAgentStorePort):
    def __init__(self, datasource: SqliteRunAgentDatasource) -> None:
        self.datasource = datasource

    def get_agent(
        self,
        *,
        run_id: str,
        agent_id: str,
    ) -> RunAgent | None:
        return self.datasource.get_agent(run_id=run_id, agent_id=agent_id)

    def get_first_agent(self, *, run_id: str) -> RunAgent | None:
        return self.datasource.get_first_agent(run_id=run_id)

    def attach_agent(
        self,
        *,
        run_id: str,
        agent_id: str,
        context_id: str,
    ) -> None:
        self.datasource.attach_agent(
            run_id=run_id,
            agent_id=agent_id,
            context_id=context_id,
        )
