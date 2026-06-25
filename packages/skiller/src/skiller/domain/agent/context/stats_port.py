from typing import Protocol

from skiller.domain.agent.context.stats_model import AgentContextObservedStats
from skiller.domain.agent.llm.model import LLMUsage


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
