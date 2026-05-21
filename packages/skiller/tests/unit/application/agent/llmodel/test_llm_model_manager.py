import pytest

from skiller.application.agent.llmodel.llm_model_manager import LLMModelManager
from skiller.domain.agent.agent_config_model import (
    AgentConfig,
    AgentLLMClientType,
    AgentLLMConfig,
    AgentLLMProviderConfig,
    AgentLLMProviderType,
)
from skiller.domain.agent.llm_model import LLMMessage, LLMRequest, LLMResponse, LLMUsage

pytestmark = pytest.mark.unit


class _FakeLLM:
    def __init__(self, response: LLMResponse) -> None:
        self.response = response
        self.calls: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return self.response


class _ClientCreator:
    def __init__(self, response: LLMResponse) -> None:
        self.response = response
        self.providers: list[AgentLLMProviderConfig] = []
        self.clients: list[_FakeLLM] = []

    def __call__(self, provider: AgentLLMProviderConfig) -> _FakeLLM:
        self.providers.append(provider)
        client = _FakeLLM(self.response)
        self.clients.append(client)
        return client


def test_llm_model_manager_creates_fake_client_on_demand() -> None:
    fake_response = LLMResponse(
        ok=True,
        content="fake",
        model="fake-response-model",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    fake_creator = _ClientCreator(fake_response)
    manager = _manager(create_fake_client=fake_creator)
    request = LLMRequest(messages=(LLMMessage.user("hello"),))
    provider = _provider(
        client_type=AgentLLMClientType.FAKE,
        provider=AgentLLMProviderType.FAKE,
        model="fake-test",
    )

    assert fake_creator.clients == []

    response = manager.generate(config=_config(provider), request=request)

    assert response == LLMResponse(
        ok=True,
        content="fake",
        model="fake-response-model",
        usage=LLMUsage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            provider="fake",
            model="fake-response-model",
        ),
    )
    assert fake_creator.providers == [provider]
    assert fake_creator.clients[0].calls == [request]


def test_llm_model_manager_reuses_client_for_same_provider() -> None:
    fake_creator = _ClientCreator(LLMResponse(ok=True, content="fake"))
    manager = _manager(create_fake_client=fake_creator)
    request = LLMRequest(messages=(LLMMessage.user("hello"),))
    provider = _provider(
        client_type=AgentLLMClientType.FAKE,
        provider=AgentLLMProviderType.FAKE,
        model="fake-test",
    )
    config = _config(provider)

    manager.generate(config=config, request=request)
    manager.generate(config=config, request=request)

    assert fake_creator.providers == [provider]
    assert len(fake_creator.clients) == 1
    assert fake_creator.clients[0].calls == [request, request]


def test_llm_model_manager_creates_openai_client_on_demand() -> None:
    openai_response = LLMResponse(ok=True, content="openai", model="gpt-test")
    openai_creator = _ClientCreator(openai_response)
    manager = _manager(create_openai_client=openai_creator)
    request = LLMRequest(messages=(LLMMessage.user("hello"),))
    provider = _provider(
        client_type=AgentLLMClientType.OPENAI_CHAT_COMPLETIONS,
        provider=AgentLLMProviderType.OPENAI,
        model="gpt-test",
    )

    response = manager.generate(config=_config(provider), request=request)

    assert response == openai_response
    assert openai_creator.providers == [provider]
    assert openai_creator.clients[0].calls == [request]


def test_llm_model_manager_uses_config_model_when_response_model_is_missing() -> None:
    fake_response = LLMResponse(
        ok=True,
        content="fake",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    fake_creator = _ClientCreator(fake_response)
    manager = _manager(create_fake_client=fake_creator)
    request = LLMRequest(messages=(LLMMessage.user("hello"),))
    provider = _provider(
        client_type=AgentLLMClientType.FAKE,
        provider=AgentLLMProviderType.FAKE,
        model="fake-config-model",
    )

    response = manager.generate(config=_config(provider), request=request)

    assert response.usage == LLMUsage(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        provider="fake",
        model="fake-config-model",
    )


def test_llm_model_manager_replaces_current_client_when_provider_changes() -> None:
    fake_creator = _ClientCreator(LLMResponse(ok=True, content="fake"))
    openai_creator = _ClientCreator(LLMResponse(ok=True, content="openai"))
    manager = _manager(
        create_fake_client=fake_creator,
        create_openai_client=openai_creator,
    )
    request = LLMRequest(messages=(LLMMessage.user("hello"),))
    fake_provider = _provider(
        client_type=AgentLLMClientType.FAKE,
        provider=AgentLLMProviderType.FAKE,
        model="fake-test",
    )
    openai_provider = _provider(
        client_type=AgentLLMClientType.OPENAI_CHAT_COMPLETIONS,
        provider=AgentLLMProviderType.OPENAI,
        model="gpt-test",
    )

    manager.generate(config=_config(fake_provider), request=request)
    manager.generate(config=_config(openai_provider), request=request)
    manager.generate(config=_config(fake_provider), request=request)

    assert fake_creator.providers == [fake_provider, fake_provider]
    assert openai_creator.providers == [openai_provider]
    assert manager.current_provider == fake_provider
    assert manager.current_client == fake_creator.clients[1]


def test_llm_model_manager_returns_error_for_unsupported_client_type() -> None:
    manager = _manager()
    provider = _provider(
        client_type=AgentLLMClientType.ANTHROPIC_MESSAGES,
        provider=AgentLLMProviderType.ANTHROPIC,
        model="claude-test",
    )

    response = manager.generate(
        config=_config(provider),
        request=LLMRequest(messages=(LLMMessage.user("hello"),)),
    )

    assert response == LLMResponse(
        ok=False,
        error="Unsupported LLM client type='anthropic_messages'.",
        error_code="unsupported_llm_client_type",
    )


def _manager(
    *,
    create_null_client: _ClientCreator | None = None,
    create_fake_client: _ClientCreator | None = None,
    create_openai_client: _ClientCreator | None = None,
) -> LLMModelManager:
    return LLMModelManager(
        create_null_client=create_null_client
        or _ClientCreator(LLMResponse(ok=False, error="null")),
        create_fake_client=create_fake_client
        or _ClientCreator(LLMResponse(ok=True, content="fake")),
        create_openai_client=create_openai_client
        or _ClientCreator(LLMResponse(ok=True, content="openai")),
    )


def _provider(
    *,
    client_type: AgentLLMClientType,
    provider: AgentLLMProviderType,
    model: str,
) -> AgentLLMProviderConfig:
    return AgentLLMProviderConfig(
        provider=provider,
        client_type=client_type,
        model=model,
        api_key="test-key",
        base_url="https://api.example.test",
        timeout_seconds=30,
        context_window_tokens=100_000,
    )


def _config(provider: AgentLLMProviderConfig) -> AgentConfig:
    return AgentConfig(
        llm=AgentLLMConfig(
            default_provider="default",
            providers={"default": provider},
        ),
    )
