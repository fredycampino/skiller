from dataclasses import replace
from typing import overload

from skiller.domain.agent.agent_llm_provider_model import (
    AgentBedrockProvider,
    AgentCodexProvider,
    AgentFakeProvider,
    AgentLLMProvider,
    AgentMiniMaxProvider,
    AgentNullProvider,
)
from skiller.domain.agent.llm_client_resolver import LLMClientResolver
from skiller.domain.agent.llm_model import LLMResponse
from skiller.domain.agent.llm_port import LLMPort, ResolvedLLMPort
from skiller.domain.agent.llm_request import (
    BedrockLLMRequest,
    CodexLLMRequest,
    LLMRequest,
    MiniMaxLLMRequest,
)


class LLMModelManager:
    def __init__(self, *, client_resolver: LLMClientResolver) -> None:
        self.client_resolver = client_resolver
        self.clients: dict[AgentLLMProvider, ResolvedLLMPort] = {}

    def generate(
        self,
        *,
        provider: AgentLLMProvider,
        request: LLMRequest,
    ) -> LLMResponse:
        if isinstance(provider, AgentMiniMaxProvider):
            if not isinstance(request, MiniMaxLLMRequest):
                raise RuntimeError("MiniMax LLM provider requires MiniMaxLLMRequest")
            client = self.client(provider)
            response = client.generate(request)
        elif isinstance(provider, AgentCodexProvider):
            if not isinstance(request, CodexLLMRequest):
                raise RuntimeError("Codex LLM provider requires CodexLLMRequest")
            client = self.client(provider)
            response = client.generate(request)
        elif isinstance(provider, AgentBedrockProvider):
            if not isinstance(request, BedrockLLMRequest):
                raise RuntimeError("Bedrock LLM provider requires BedrockLLMRequest")
            client = self.client(provider)
            response = client.generate(request)
        else:
            client = self.client(provider)
            response = client.generate(request)

        return _response_with_usage_metadata(
            response=response,
            provider=provider,
        )

    @overload
    def client(self, provider: AgentMiniMaxProvider) -> LLMPort[MiniMaxLLMRequest]: ...

    @overload
    def client(self, provider: AgentCodexProvider) -> LLMPort[CodexLLMRequest]: ...

    @overload
    def client(self, provider: AgentBedrockProvider) -> LLMPort[BedrockLLMRequest]: ...

    @overload
    def client(self, provider: AgentFakeProvider | AgentNullProvider) -> LLMPort[LLMRequest]: ...

    @overload
    def client(self, provider: AgentLLMProvider) -> ResolvedLLMPort: ...

    def client(self, provider: AgentLLMProvider) -> ResolvedLLMPort:
        client = self.clients.get(provider)
        if client is not None:
            return client

        client = self.client_resolver.resolve(provider)
        self.clients[provider] = client
        return client


def _response_with_usage_metadata(
    *,
    response: LLMResponse,
    provider: AgentLLMProvider,
) -> LLMResponse:
    usage = response.usage
    if usage is None:
        return response

    usage = replace(
        usage,
        provider=provider.type,
        model=response.model,
    )
    return replace(
        response,
        usage=usage,
    )
