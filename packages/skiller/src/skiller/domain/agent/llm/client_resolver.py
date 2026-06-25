from typing import Protocol, overload

from skiller.domain.agent.llm.port import LLMPort, ResolvedLLMPort
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.agent.llm.provider_lmstudio import LMStudioLLMRequest
from skiller.domain.agent.llm.provider_minimax import MiniMaxLLMRequest
from skiller.domain.agent.llm.provider_registry import (
    AgentBedrockProvider,
    AgentCodexProvider,
    AgentFakeProvider,
    AgentLLMProvider,
    AgentLMStudioProvider,
    AgentMiniMaxProvider,
    AgentNullProvider,
)
from skiller.domain.agent.llm.request import LLMRequest


class LLMClientResolver(Protocol):
    @overload
    def resolve(self, provider: AgentMiniMaxProvider) -> LLMPort[MiniMaxLLMRequest]: ...

    @overload
    def resolve(self, provider: AgentLMStudioProvider) -> LLMPort[LMStudioLLMRequest]: ...

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
