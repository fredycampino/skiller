from skiller.domain.agent.context.context_state_port import AgentContextStatePort
from skiller.domain.agent.context.model import AgentContextState
from skiller.infrastructure.db.datasource.sqlite_agent_context_state_datasource import (
    SqliteAgentContextStateDatasource,
)


class SqliteAgentContextStatePort(AgentContextStatePort):
    def __init__(self, datasource: SqliteAgentContextStateDatasource) -> None:
        self.datasource = datasource

    def get_state(self, *, context_id: str) -> AgentContextState:
        state = self.datasource.get_state(context_id=context_id)
        if state is not None:
            return state
        return AgentContextState(
            context_id=context_id,
            start_sequence=1,
            compacted_sequence=None,
            compaction_id=0,
        )

    def save_state(self, *, state: AgentContextState) -> None:
        self.datasource.save_state(state=state)
