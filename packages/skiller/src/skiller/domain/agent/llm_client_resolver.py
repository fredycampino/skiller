from typing import Protocol

from skiller.domain.agent.agent_llm_provider_model import AgentLLMProvider
from skiller.domain.agent.llm_port import LLMPort


class LLMClientResolver(Protocol):
    def resolve(self, provider: AgentLLMProvider) -> LLMPort:
        pass
