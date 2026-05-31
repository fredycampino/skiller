from typing import Protocol

from skiller.domain.agent.agent_stats_model import AgentContextObservedStats
from skiller.domain.agent.llm_model import LLMUsage


class AgentContextStatsPort(Protocol):
    def get_stats(
        self,
        *,
        context_id: str,
    ) -> AgentContextObservedStats: ...

    def get_usage(
        self,
        *,
        context_id: str,
    ) -> LLMUsage: ...
