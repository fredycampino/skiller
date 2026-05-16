from dataclasses import dataclass

from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.agent.runner_state import AgentRunnerState
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.llm_model import LLMRequest


@dataclass(frozen=True)
class AgentContextLLMRequest:
    turn_id: str
    llm_request: LLMRequest


class AgentContextManager:
    def __init__(
        self,
        *,
        agent_context_store: AgentContextStorePort,
        prompt_builder: AgentPromptBuilder,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.prompt_builder = prompt_builder

    def build_llm_request(
        self,
        *,
        state: AgentRunnerState,
    ) -> AgentContextLLMRequest:
        entries = self.agent_context_store.list_entries(scope=state)
        turn_id = self.agent_context_store.next_turn_id(scope=state)
        llm_request = self.prompt_builder.build_request(
            system=state.config.system,
            entries=entries,
            tools=state.enabled_tools,
        )
        return AgentContextLLMRequest(
            turn_id=turn_id,
            llm_request=llm_request,
        )
