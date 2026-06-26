import pytest

from skiller.application.agent.llmodel.llm_model_manager import LLMModelManager
from skiller.domain.agent.llm.model import (
    LLMCustomModel,
    LLMResponse,
    LLMUsage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_registry import (
    BEDROCK_MODELS,
    CODEX_MODELS,
    FAKE_MODELS,
    MINIMAX_MODELS,
    AgentBedrockLLMModel,
    AgentBedrockProvider,
    AgentCodexLLMModel,
    AgentCodexProvider,
    AgentFakeLLMModel,
    AgentFakeProvider,
    AgentLLMProvider,
    AgentLMStudioProvider,
    AgentMiniMaxLLMModel,
    AgentMiniMaxProvider,
)
from skiller.domain.agent.llm.request import LLMRequest

pytestmark = pytest.mark.unit


def _lmstudio_model() -> LLMCustomModel:
    return LLMCustomModel(
        value="google/gemma-4-12b-qat",
        model_context_window_tokens=131_072,
    )


class _FakeLLM:
    def __init__(self, response: LLMResponse) -> None:
        self.response = response
        self.calls: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return self.response


class _FakeClientResolver:
    def __init__(self, response: LLMResponse) -> None:
        self.providers: list[AgentLLMProvider] = []
        self.client = _FakeLLM(response)

    def resolve(self, provider: AgentLLMProvider) -> _FakeLLM:
        self.providers.append(provider)
        return self.client


def test_llm_model_manager_uses_factory_client() -> None:
    provider = _provider()
    request = _request()
    client_resolver = _FakeClientResolver(
        LLMResponse(ok=True, model=AgentFakeLLMModel.MODEL1, content="fake")
    )
    manager = LLMModelManager(client_resolver=client_resolver)

    response = manager.generate(provider=provider, request=request)

    assert response == LLMResponse(
        ok=True,
        model=AgentFakeLLMModel.MODEL1,
        content="fake",
    )
    assert client_resolver.providers == [provider]
    assert client_resolver.client.calls == [request]


def test_llm_model_manager_reuses_client_for_same_provider() -> None:
    provider = _provider()
    request = _request()
    client_resolver = _FakeClientResolver(
        LLMResponse(ok=True, model=AgentFakeLLMModel.MODEL1, content="fake")
    )
    manager = LLMModelManager(client_resolver=client_resolver)

    manager.generate(provider=provider, request=request)
    manager.generate(provider=provider, request=request)

    assert client_resolver.providers == [provider]
    assert client_resolver.client.calls == [request, request]


def test_llm_model_manager_adds_provider_usage_metadata() -> None:
    provider = _provider(model=AgentFakeLLMModel.MODEL1)
    response = LLMResponse(
        ok=True,
        model=AgentFakeLLMModel.MODEL1,
        content="fake",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    manager = LLMModelManager(client_resolver=_FakeClientResolver(response))

    result = manager.generate(
        provider=provider,
        request=_request(),
    )

    assert result.usage == LLMUsage(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        provider="fake",
        model=AgentFakeLLMModel.MODEL1,
    )


@pytest.mark.parametrize(
    ("provider", "error"),
    [
        (
            AgentMiniMaxProvider(
                model=AgentMiniMaxLLMModel.M2_7,
                models=MINIMAX_MODELS,
                api_key="secret",
                timeout_seconds=30,
                window_width_tokens=100_000,
            ),
            "MiniMax LLM provider requires MiniMaxLLMRequest",
        ),
        (
            AgentLMStudioProvider(
                model=_lmstudio_model(),
                models=(_lmstudio_model(),),
                timeout_seconds=30,
                window_width_tokens=131_072,
            ),
            "LM Studio LLM provider requires LMStudioLLMRequest",
        ),
        (
            AgentCodexProvider(
                model=AgentCodexLLMModel.GPT_5_5,
                models=CODEX_MODELS,
                credentials_file="/tmp/openai-codex.json",
                timeout_seconds=120,
                window_width_tokens=100_000,
            ),
            "Codex LLM provider requires CodexLLMRequest",
        ),
        (
            AgentBedrockProvider(
                model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
                models=BEDROCK_MODELS,
                profile="claude-bedrock",
                timeout_seconds=120,
                window_width_tokens=100_000,
            ),
            "Bedrock LLM provider requires BedrockLLMRequest",
        ),
    ],
)
def test_llm_model_manager_rejects_provider_request_mismatch(
    provider: AgentLLMProvider,
    error: str,
) -> None:
    client_resolver = _FakeClientResolver(
        LLMResponse(ok=True, model=AgentFakeLLMModel.MODEL1)
    )
    manager = LLMModelManager(client_resolver=client_resolver)

    with pytest.raises(RuntimeError, match=error):
        manager.generate(provider=provider, request=_request())

    assert client_resolver.providers == []


def _provider(
    *,
    model: AgentFakeLLMModel = AgentFakeLLMModel.MODEL1,
) -> AgentLLMProvider:
    return AgentFakeProvider(
        model=model,
        models=FAKE_MODELS,
        timeout_seconds=30,
        window_width_tokens=100_000,
    )


def _request() -> LLMRequest:
    return LLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=AgentFakeLLMModel.MODEL1,
    )
