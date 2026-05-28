from dataclasses import replace

from skiller.domain.agent.agent_llm_provider_model import AgentLLMProvider
from skiller.domain.agent.llm_client_resolver import LLMClientResolver
from skiller.domain.agent.llm_model import LLMRequest, LLMResponse
from skiller.domain.agent.llm_port import LLMPort


class LLMModelManager:
    def __init__(self, *, client_resolver: LLMClientResolver) -> None:
        self.client_resolver = client_resolver
        self.clients: dict[AgentLLMProvider, LLMPort] = {}

    def generate(
        self,
        *,
        provider: AgentLLMProvider,
        request: LLMRequest,
    ) -> LLMResponse:
        client = self.client(provider)
        response = client.generate(request)
        return _response_with_usage_metadata(
            response=response,
            provider=provider,
        )

    def client(self, provider: AgentLLMProvider) -> LLMPort:
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
