from skiller.application.use_cases.agent.get_agent_stats import (
    GetAgentStatsResult,
    GetAgentStatsUseCase,
)
from skiller.application.use_cases.agent.interrupt_agent import (
    InterruptAgentResult,
    InterruptAgentUseCase,
)
from skiller.application.use_cases.agent.list_agent_models import (
    ListAgentModelsResult,
    ListAgentModelsUseCase,
)


class AgentApplicationService:
    def __init__(
        self,
        interrupt_agent_use_case: InterruptAgentUseCase,
        get_agent_stats_use_case: GetAgentStatsUseCase,
        list_agent_models_use_case: ListAgentModelsUseCase,
    ) -> None:
        self.interrupt_agent_use_case = interrupt_agent_use_case
        self.get_agent_stats_use_case = get_agent_stats_use_case
        self.list_agent_models_use_case = list_agent_models_use_case

    def interrupt_agent(self, run_id: str) -> InterruptAgentResult:
        return self.interrupt_agent_use_case.execute(run_id)

    def get_agent_stats(self, run_id: str, agent_id: str) -> GetAgentStatsResult:
        return self.get_agent_stats_use_case.execute(run_id, agent_id)

    def list_agent_models(self, run_id: str) -> ListAgentModelsResult:
        return self.list_agent_models_use_case.execute(run_id)
