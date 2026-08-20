from skiller.application.use_cases.agent.get_agent_stats import (
    GetAgentStatsResult,
    GetAgentStatsUseCase,
)
from skiller.application.use_cases.agent.get_agent_tools import (
    GetAgentToolsResult,
    GetAgentToolsUseCase,
)
from skiller.application.use_cases.agent.interrupt_agent import (
    InterruptAgentResult,
    InterruptAgentUseCase,
)
from skiller.application.use_cases.agent.list_agent_context import (
    ListAgentContextResult,
    ListAgentContextUseCase,
)
from skiller.application.use_cases.agent.list_agent_models import (
    ListAgentModelsResult,
    ListAgentModelsUseCase,
)
from skiller.application.use_cases.agent.list_llm_providers import (
    ListLLMProvidersResult,
    ListLLMProvidersUseCase,
)
from skiller.application.use_cases.agent.select_agent_model import (
    SelectAgentModelResult,
    SelectAgentModelUseCase,
)


class AgentApplicationService:
    def __init__(
        self,
        interrupt_agent_use_case: InterruptAgentUseCase,
        get_agent_stats_use_case: GetAgentStatsUseCase,
        list_agent_context_use_case: ListAgentContextUseCase,
        list_agent_models_use_case: ListAgentModelsUseCase,
        list_llm_providers_use_case: ListLLMProvidersUseCase,
        get_agent_tools_use_case: GetAgentToolsUseCase,
        select_agent_model_use_case: SelectAgentModelUseCase,
    ) -> None:
        self.interrupt_agent_use_case = interrupt_agent_use_case
        self.get_agent_stats_use_case = get_agent_stats_use_case
        self.list_agent_context_use_case = list_agent_context_use_case
        self.list_agent_models_use_case = list_agent_models_use_case
        self.list_llm_providers_use_case = list_llm_providers_use_case
        self.get_agent_tools_use_case = get_agent_tools_use_case
        self.select_agent_model_use_case = select_agent_model_use_case

    def interrupt_agent(self, run_id: str) -> InterruptAgentResult:
        return self.interrupt_agent_use_case.execute(run_id)

    def get_agent_stats(self, run_id: str, agent_id: str) -> GetAgentStatsResult:
        return self.get_agent_stats_use_case.execute(run_id, agent_id)

    def list_agent_context(self, run_id: str, agent_id: str) -> ListAgentContextResult:
        return self.list_agent_context_use_case.execute(run_id, agent_id)

    def list_agent_models(self, run_id: str) -> ListAgentModelsResult:
        return self.list_agent_models_use_case.execute(run_id)

    def list_llm_providers(self) -> ListLLMProvidersResult:
        return self.list_llm_providers_use_case.execute()

    def get_agent_tools(self, run_id: str) -> GetAgentToolsResult:
        return self.get_agent_tools_use_case.execute(run_id)

    def select_agent_model(
        self,
        *,
        run_id: str,
        provider: str,
        model: str,
    ) -> SelectAgentModelResult:
        return self.select_agent_model_use_case.execute(
            run_id=run_id,
            provider=provider,
            model=model,
        )
