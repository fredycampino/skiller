from typing import Protocol, overload

from skiller.domain.agent.agent_llm_provider_model import (
    AgentBedrockProvider,
    AgentCodexProvider,
    AgentFakeProvider,
    AgentLLMProvider,
    AgentMiniMaxProvider,
    AgentNullProvider,
)
from skiller.domain.agent.llm_port import LLMPort, ResolvedLLMPort
from skiller.domain.agent.llm_request import (
    BedrockLLMRequest,
    CodexLLMRequest,
    LLMRequest,
    MiniMaxLLMRequest,
)


class LLMClientResolver(Protocol):
    @overload
    def resolve(self, provider: AgentMiniMaxProvider) -> LLMPort[MiniMaxLLMRequest]: ...

    @overload
    def resolve(self, provider: AgentCodexProvider) -> LLMPort[CodexLLMRequest]: ...

    @overload
    def resolve(self, provider: AgentBedrockProvider) -> LLMPort[BedrockLLMRequest]: ...

    @overload
    def resolve(
        self,
        provider: AgentFakeProvider | AgentNullProvider,
    ) -> LLMPort[LLMRequest]: ...

    @overload
    def resolve(self, provider: AgentLLMProvider) -> ResolvedLLMPort: ...

    def resolve(self, provider: AgentLLMProvider) -> ResolvedLLMPort:
        pass
