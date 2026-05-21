from collections.abc import Callable
from dataclasses import replace

from skiller.domain.agent.agent_config_model import (
    AgentConfig,
    AgentLLMClientType,
    AgentLLMProviderConfig,
)
from skiller.domain.agent.llm_model import LLMRequest, LLMResponse
from skiller.domain.agent.llm_port import LLMPort

LLMClientCreator = Callable[[AgentLLMProviderConfig], LLMPort]


class LLMModelManager:
    def __init__(
        self,
        *,
        create_null_client: LLMClientCreator,
        create_fake_client: LLMClientCreator,
        create_openai_client: LLMClientCreator,
    ) -> None:
        self.client_creators: dict[AgentLLMClientType, LLMClientCreator] = {
            AgentLLMClientType.NULL: create_null_client,
            AgentLLMClientType.FAKE: create_fake_client,
            AgentLLMClientType.OPENAI_CHAT_COMPLETIONS: create_openai_client,
        }
        self.current_provider: AgentLLMProviderConfig | None = None
        self.current_client: LLMPort | None = None

    def generate(
        self,
        *,
        config: AgentConfig,
        request: LLMRequest,
    ) -> LLMResponse:
        provider = config.llm.default()
        if self.current_provider == provider and self.current_client is not None:
            response = self.current_client.generate(request)
            return _response_with_usage_metadata(response=response, provider=provider)

        client_creator = self.client_creators.get(provider.client_type)
        if client_creator is None:
            return LLMResponse(
                ok=False,
                error=f"Unsupported LLM client type='{provider.client_type.value}'.",
                error_code="unsupported_llm_client_type",
            )

        client = client_creator(provider)
        self.current_provider = provider
        self.current_client = client
        response = client.generate(request)
        return _response_with_usage_metadata(response=response, provider=provider)


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
        provider=provider.provider.value,
        model=model,
    )
    return replace(
        response,
        usage=usage,
    )
