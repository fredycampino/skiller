from dataclasses import replace
from typing import overload

from skiller.domain.agent.llm.client_resolver import LLMClientResolver
from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort, ResolvedLLMPort
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_catalog import (
    BedrockLLMProviderDefinition,
    CodexLLMProviderDefinition,
    LLMProviderDefinition,
    OpenAILLMProviderDefinition,
)
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.agent.llm.request import LLMRequest, OpenAILLMRequest


class LLMModelManager:
    def __init__(self, *, client_resolver: LLMClientResolver) -> None:
        self.client_resolver = client_resolver
        self.clients: dict[str, tuple[LLMProviderDefinition, ResolvedLLMPort]] = {}

    def generate(
        self,
        *,
        provider: LLMProviderDefinition,
        request: LLMRequest,
    ) -> LLMResponse:
        if isinstance(provider, OpenAILLMProviderDefinition):
            if not isinstance(request, OpenAILLMRequest):
                raise RuntimeError("OpenAI LLM adapter requires OpenAILLMRequest")
            client = self.client(provider)
            response = client.generate(request)
        elif isinstance(provider, CodexLLMProviderDefinition):
            if not isinstance(request, CodexLLMRequest):
                raise RuntimeError("Codex LLM provider requires CodexLLMRequest")
            client = self.client(provider)
            response = client.generate(request)
        elif isinstance(provider, BedrockLLMProviderDefinition):
            if not isinstance(request, BedrockLLMRequest):
                raise RuntimeError("Bedrock LLM provider requires BedrockLLMRequest")
            client = self.client(provider)
            response = client.generate(request)
        else:
            raise RuntimeError(f"Unsupported LLM adapter: {provider.adapter}")

        return _response_with_usage_metadata(
            response=response,
            provider=provider,
        )

    @overload
    def client(self, provider: OpenAILLMProviderDefinition) -> LLMPort[OpenAILLMRequest]: ...

    @overload
    def client(self, provider: CodexLLMProviderDefinition) -> LLMPort[CodexLLMRequest]: ...

    @overload
    def client(self, provider: BedrockLLMProviderDefinition) -> LLMPort[BedrockLLMRequest]: ...

    @overload
    def client(self, provider: LLMProviderDefinition) -> ResolvedLLMPort: ...

    def client(self, provider: LLMProviderDefinition) -> ResolvedLLMPort:
        cached = self.clients.get(provider.name)
        if cached is not None and cached[0] == provider:
            return cached[1]

        client = self.client_resolver.resolve(provider)
        self.clients[provider.name] = (provider, client)
        return client


def _response_with_usage_metadata(
    *,
    response: LLMResponse,
    provider: LLMProviderDefinition,
) -> LLMResponse:
    usage = response.usage
    if usage is None:
        return response

    usage = replace(
        usage,
        provider=provider.name,
        model=response.model,
    )
    return replace(
        response,
        usage=usage,
    )
