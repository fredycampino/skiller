from skiller.application.use_cases.agent.get_agent_stats import (
    GetAgentStatsResult,
    GetAgentStatsUseCase,
)
from skiller.application.use_cases.agent.interrupt_agent import (
    InterruptAgentResult,
    InterruptAgentUseCase,
)


class AgentApplicationService:
    def __init__(
        self,
        interrupt_agent_use_case: InterruptAgentUseCase,
        get_agent_stats_use_case: GetAgentStatsUseCase,
    ) -> None:
        self.interrupt_agent_use_case = interrupt_agent_use_case
        self.get_agent_stats_use_case = get_agent_stats_use_case

    def interrupt_agent(self, run_id: str) -> InterruptAgentResult:
        return self.interrupt_agent_use_case.execute(run_id)

    def get_agent_stats(self, run_id: str, agent_id: str) -> GetAgentStatsResult:
        return self.get_agent_stats_use_case.execute(run_id, agent_id)
