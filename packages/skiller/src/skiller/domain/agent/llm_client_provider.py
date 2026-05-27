from typing import Protocol

from skiller.domain.agent.agent_config_model import AgentLLMProviderConfig
from skiller.domain.agent.llm_port import LLMPort


class LLMClientProvider(Protocol):
    def create(self, provider: AgentLLMProviderConfig) -> LLMPort:
        pass
