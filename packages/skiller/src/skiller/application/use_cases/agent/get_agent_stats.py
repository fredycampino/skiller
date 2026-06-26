from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from skiller.domain.agent.config.port import AgentConfigPort
from skiller.domain.agent.context.stats_model import (
    AgentContextStats,
    AgentContextWindowStats,
    AgentStats,
)
from skiller.domain.agent.context.stats_port import AgentContextStatsPort
from skiller.domain.run.run_agent_store_port import RunAgentStorePort
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.runner_port import RunnerPort


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
        skill_runner: RunnerPort,
    ) -> None:
        self.run_store = run_store
        self.run_agent_store = run_agent_store
        self.context_stats = context_stats
        self.agent_config = agent_config
        self.skill_runner = skill_runner

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
        config_path = self._resolve_agent_config_path(run.source, run.ref)
        config = self.agent_config.get_config(config_path=config_path)
        provider = config.llm.default()
        capacity_tokens = provider.model_max_tokens
        limit_tokens = provider.context_max_tokens(
            ratio=config.context.compaction.max_total_tokens_ratio,
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

    def _resolve_agent_config_path(self, source: str, ref: str) -> Path | None:
        try:
            config_path = self.skill_runner.resolve_file_path(
                source,
                ref,
                "agent.json",
            )
        except (FileNotFoundError, ValueError):
            return None

        if config_path.exists():
            return config_path
        return None
