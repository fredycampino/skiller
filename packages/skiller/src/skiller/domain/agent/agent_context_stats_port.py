from typing import Protocol

from skiller.domain.agent.agent_run_scope import AgentRunScope
from skiller.domain.agent.agent_stats_model import AgentContextStats
from skiller.domain.agent.llm_model import LLMUsage


class AgentContextStatsPort(Protocol):
    def get_stats(
        self,
        *,
        scope: AgentRunScope,
    ) -> AgentContextStats: ...

    def get_usage(
        self,
        *,
        scope: AgentRunScope,
    ) -> LLMUsage: ...
