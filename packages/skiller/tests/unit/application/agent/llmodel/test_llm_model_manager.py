import pytest

from skiller.application.agent.llmodel.llm_model_manager import LLMModelManager
from skiller.domain.agent.agent_config_model import (
    AgentLLMProviderConfig,
    AgentLLMProviderType,
)
from skiller.domain.agent.llm_model import (
    LLMRequest,
    LLMResponse,
    LLMUsage,
    LLMUserMessage,
)

pytestmark = pytest.mark.unit


class _FakeLLM:
    def __init__(self, response: LLMResponse) -> None:
        self.response = response
        self.calls: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return self.response


class _FakeClientProvider:
    def __init__(self, response: LLMResponse) -> None:
        self.providers: list[AgentLLMProviderConfig] = []
        self.client = _FakeLLM(response)

    def create(self, provider: AgentLLMProviderConfig) -> _FakeLLM:
        self.providers.append(provider)
        return self.client


def test_llm_model_manager_uses_factory_client() -> None:
    provider = _provider()
    request = LLMRequest(messages=(LLMUserMessage("hello"),), model="model1")
    client_provider = _FakeClientProvider(LLMResponse(ok=True, content="fake"))
    manager = LLMModelManager(client_provider=client_provider)

    response = manager.generate(provider=provider, request=request)

    assert response == LLMResponse(ok=True, content="fake")
    assert client_provider.providers == [provider]
    assert client_provider.client.calls == [request]


def test_llm_model_manager_reuses_client_for_same_provider() -> None:
    provider = _provider()
    request = LLMRequest(messages=(LLMUserMessage("hello"),), model="model1")
    client_provider = _FakeClientProvider(LLMResponse(ok=True, content="fake"))
    manager = LLMModelManager(client_provider=client_provider)

    manager.generate(provider=provider, request=request)
    manager.generate(provider=provider, request=request)

    assert client_provider.providers == [provider]
    assert client_provider.client.calls == [request, request]


def test_llm_model_manager_adds_provider_usage_metadata() -> None:
    provider = _provider(model="model1")
    response = LLMResponse(
        ok=True,
        content="fake",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    manager = LLMModelManager(client_provider=_FakeClientProvider(response))

    result = manager.generate(
        provider=provider,
        request=LLMRequest(messages=(LLMUserMessage("hello"),), model="model1"),
    )

    assert result.usage == LLMUsage(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        provider="fake",
        model="model1",
    )


def _provider(
    *,
    model: str = "model1",
) -> AgentLLMProviderConfig:
    return AgentLLMProviderConfig(
        provider_type=AgentLLMProviderType.FAKE,
        model=model,
        api_key="test-key",
        timeout_seconds=30,
        context_window_tokens=100_000,
    )
