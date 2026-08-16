from typing import Protocol, overload

from skiller.domain.agent.llm.port import LLMPort, ResolvedLLMPort
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_catalog import (
    BedrockLLMProviderDefinition,
    CodexLLMProviderDefinition,
    LLMProviderDefinition,
    OpenAILLMProviderDefinition,
)
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.agent.llm.request import OpenAILLMRequest


class LLMClientResolver(Protocol):
    @overload
    def resolve(self, provider: OpenAILLMProviderDefinition) -> LLMPort[OpenAILLMRequest]: ...

    @overload
    def resolve(self, provider: CodexLLMProviderDefinition) -> LLMPort[CodexLLMRequest]: ...

    @overload
    def resolve(self, provider: BedrockLLMProviderDefinition) -> LLMPort[BedrockLLMRequest]: ...

    @overload
    def resolve(self, provider: LLMProviderDefinition) -> ResolvedLLMPort: ...

    def resolve(self, provider: LLMProviderDefinition) -> ResolvedLLMPort:
        pass
