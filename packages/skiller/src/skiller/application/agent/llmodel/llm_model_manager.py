from dataclasses import replace

from skiller.domain.agent.agent_config_model import AgentLLMProviderConfig
from skiller.domain.agent.llm_client_provider import LLMClientProvider
from skiller.domain.agent.llm_model import LLMRequest, LLMResponse
from skiller.domain.agent.llm_port import LLMPort


class LLMModelManager:
    def __init__(self, *, client_provider: LLMClientProvider) -> None:
        self.client_provider = client_provider
        self.clients: dict[AgentLLMProviderConfig, LLMPort] = {}

    def generate(
        self,
        *,
        provider: AgentLLMProviderConfig,
        request: LLMRequest,
    ) -> LLMResponse:
        client = self.client(provider)
        response = client.generate(request)
        return _response_with_usage_metadata(
            response=response,
            provider=provider,
        )

    def client(self, provider: AgentLLMProviderConfig) -> LLMPort:
        client = self.clients.get(provider)
        if client is not None:
            return client

        client = self.client_provider.create(provider)
        self.clients[provider] = client
        return client


def _response_with_usage_metadata(
    *,
    response: LLMResponse,
    provider: AgentLLMProviderConfig,
) -> LLMResponse:
    usage = response.usage
    if usage is None:
        return response

    model = response.model or provider.model
    usage = replace(
        usage,
        provider=provider.provider_type.value,
        model=model,
    )
    return replace(
        response,
        usage=usage,
    )
