from dataclasses import dataclass
from enum import Enum

from skiller.domain.agent.config.agent_config_port import AgentConfigPort
from skiller.domain.agent.config.file_selection import snapshot_agent_config_file
from skiller.domain.agent.context.stats_model import (
    AgentContextStats,
    AgentContextWindowStats,
    AgentStats,
)
from skiller.domain.agent.context.stats_port import AgentContextStatsPort
from skiller.domain.agent.llm.provider_catalog_port import LLMProviderCatalogPort
from skiller.domain.run.run_agent_store_port import RunAgentStorePort
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


class GetAgentStatsUseCase:
    def __init__(
        self,
        *,
        run_store: RunStorePort,
        run_agent_store: RunAgentStorePort,
        context_stats: AgentContextStatsPort,
        agent_config: AgentConfigPort,
        llm_provider_catalog: LLMProviderCatalogPort,
    ) -> None:
        self.run_store = run_store
        self.run_agent_store = run_agent_store
        self.context_stats = context_stats
        self.agent_config = agent_config
        self.llm_provider_catalog = llm_provider_catalog

    def execute(self, run_id: str, agent_id: str) -> GetAgentStatsResult:
        if not run_id or not agent_id:
            raise RuntimeError("GetAgentStatsUseCase requires run_id and agent_id")

        run = self.run_store.get_run(run_id)
        if run is None:
            return GetAgentStatsResult(
                status=GetAgentStatsStatus.RUN_NOT_FOUND,
                run_id=run_id,
                agent_id=agent_id,
                error=f"Run '{run_id}' not found",
            )

        agent = self.run_agent_store.get_agent(run_id=run_id, agent_id=agent_id)
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

        context_stats = self.context_stats.get_stats(context_id=agent.context_id)
        config_path = self.agent_config.resolve_config_path(
            flow_dir=run.flow_path.parent,
            file_reference=snapshot_agent_config_file(run.snapshot),
        )
        config = self.agent_config.get_config(
            flow_dir=run.flow_path.parent, config_path=config_path
        )
        catalog = self.llm_provider_catalog.get_catalog()
        model = catalog.get_model(
            provider_name=config.llm.provider,
            model_name=config.llm.model,
        )
        context_config = config.context
        capacity_tokens = context_config.effective_context_tokens(
            model_context_window_tokens=model.context_window_tokens,
        )
        limit_tokens = context_config.compaction_trigger_tokens(
            model_context_window_tokens=model.context_window_tokens,
        )
        return GetAgentStatsResult(
            status=GetAgentStatsStatus.OK,
            run_id=run_id,
            agent_id=agent_id,
            stats=AgentStats(
                run_id=run_id,
                agent_id=agent_id,
                context_id=agent.context_id,
                context=AgentContextStats(
                    entries=context_stats.entries,
                    estimated_tokens=context_stats.estimated_tokens,
                    window=AgentContextWindowStats(
                        start_sequence=context_stats.window.start_sequence,
                        end_sequence=context_stats.window.end_sequence,
                        current_tokens=context_stats.window.current_tokens,
                        limit_tokens=limit_tokens,
                        capacity_tokens=capacity_tokens,
                    ),
                ),
            ),
        )
