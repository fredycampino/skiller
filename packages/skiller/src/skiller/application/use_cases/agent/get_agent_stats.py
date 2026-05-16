from dataclasses import dataclass
from enum import Enum

from skiller.domain.agent.agent_context_stats_port import AgentContextStatsPort
from skiller.domain.agent.agent_stats_model import AgentStats
from skiller.domain.run.run_store_port import RunStorePort


class GetAgentStatsStatus(str, Enum):
    OK = "OK"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    AGENT_CONTEXT_NOT_READY = "AGENT_CONTEXT_NOT_READY"


@dataclass(frozen=True)
class GetAgentStatsResult:
    status: GetAgentStatsStatus
    run_id: str
    agent_id: str
    stats: AgentStats | None = None
    error: str | None = None


@dataclass(frozen=True)
class _AgentStatsScope:
    run_id: str
    agent_id: str
    context_id: str


class GetAgentStatsUseCase:
    def __init__(
        self,
        *,
        store: RunStorePort,
        context_stats: AgentContextStatsPort,
    ) -> None:
        self.store = store
        self.context_stats = context_stats

    def execute(self, run_id: str, agent_id: str) -> GetAgentStatsResult:
        if not run_id or not agent_id:
            raise RuntimeError("GetAgentStatsUseCase requires run_id and agent_id")

        run = self.store.get_run(run_id)
        if run is None:
            return GetAgentStatsResult(
                status=GetAgentStatsStatus.RUN_NOT_FOUND,
                run_id=run_id,
                agent_id=agent_id,
                error=f"Run '{run_id}' not found",
            )

        agent = self.store.get_agent(run_id=run_id, agent_id=agent_id)
        if agent is None:
            return GetAgentStatsResult(
                status=GetAgentStatsStatus.AGENT_NOT_FOUND,
                run_id=run_id,
                agent_id=agent_id,
                error=f"Agent '{agent_id}' not found in run '{run_id}'",
            )
        if not agent.context_id:
            return GetAgentStatsResult(
                status=GetAgentStatsStatus.AGENT_CONTEXT_NOT_READY,
                run_id=run_id,
                agent_id=agent_id,
                error=f"Agent '{agent_id}' has no attached context in run '{run_id}'",
            )

        scope = _AgentStatsScope(
            run_id=run_id,
            agent_id=agent_id,
            context_id=agent.context_id,
        )
        context_stats = self.context_stats.get_stats(scope=scope)
        return GetAgentStatsResult(
            status=GetAgentStatsStatus.OK,
            run_id=run_id,
            agent_id=agent_id,
            stats=AgentStats(
                run_id=run_id,
                agent_id=agent_id,
                context_id=agent.context_id,
                context=context_stats,
            ),
        )
