import pytest

from skiller.application.agent.llmodel.llm_model_manager import LLMModelManager
from skiller.domain.agent.llm.model import (
    LLMResponse,
    LLMToolChoiceMode,
    LLMUsage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_catalog import (
    BedrockLLMProviderDefinition,
    CodexLLMProviderDefinition,
    LLMModelDefinition,
    LLMProviderDefinition,
    OpenAILLMProviderDefinition,
)
from skiller.domain.agent.llm.request import LLMRequest, OpenAILLMRequest

pytestmark = pytest.mark.unit


MODEL = LLMModelDefinition(model="model1", context_window_tokens=100_000)
MODEL_2 = LLMModelDefinition(model="model2", context_window_tokens=200_000)


class _FakeLLM:
    def __init__(self, response: LLMResponse) -> None:
        self.response = response
        self.calls: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return self.response


class _FakeClientResolver:
    def __init__(self, response: LLMResponse) -> None:
        self.providers: list[LLMProviderDefinition] = []
        self.client = _FakeLLM(response)

    def resolve(self, provider: LLMProviderDefinition) -> _FakeLLM:
        self.providers.append(provider)
        return self.client


def _provider() -> OpenAILLMProviderDefinition:
    return OpenAILLMProviderDefinition(
        name="fake",
        timeout_seconds=30,
        models=(MODEL, MODEL_2),
        enabled=True,
        base_url="http://localhost/v1",
        temperature=0,
        top_p=1,
        max_output_tokens=4096,
        parallel_tool_calls=True,
        tool_choice=LLMToolChoiceMode.AUTO,
        api_key_source=None,
        options={},
    )


def test_llm_model_manager_uses_factory_client() -> None:
    provider = _provider()
    request = _request()
    client_resolver = _FakeClientResolver(LLMResponse(ok=True, model=MODEL, content="fake"))
    manager = LLMModelManager(client_resolver=client_resolver)

    response = manager.generate(provider=provider, request=request)

    assert response == LLMResponse(
        ok=True,
        model=MODEL,
        content="fake",
    )
    assert client_resolver.providers == [provider]
    assert client_resolver.client.calls == [request]


def test_llm_model_manager_reuses_client_when_only_model_changes() -> None:
    provider = _provider()
    request = _request()
    second_request = _request(model=MODEL_2)
    client_resolver = _FakeClientResolver(LLMResponse(ok=True, model=MODEL, content="fake"))
    manager = LLMModelManager(client_resolver=client_resolver)

    manager.generate(provider=provider, request=request)
    manager.generate(provider=provider, request=second_request)

    assert client_resolver.providers == [provider]
    assert client_resolver.client.calls == [request, second_request]


def test_llm_model_manager_adds_provider_usage_metadata() -> None:
    provider = _provider()
    response = LLMResponse(
        ok=True,
        model=MODEL,
        content="fake",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=10,
            output_tokens=5,
            total_tokens=15,
        ),
    )
    manager = LLMModelManager(client_resolver=_FakeClientResolver(response))

    result = manager.generate(
        provider=provider,
        request=_request(),
    )

    assert result.usage == LLMUsage(
        estimated_system_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        prompt_tokens=10,
        output_tokens=5,
        total_tokens=15,
        provider="fake",
        model=MODEL,
    )


@pytest.mark.parametrize(
    ("provider", "error"),
    [
        (
            _provider(),
            "OpenAI LLM adapter requires OpenAILLMRequest",
        ),
        (
            CodexLLMProviderDefinition(
                name="codex",
                models=(MODEL,),
                enabled=True,
                credentials_file="/tmp/openai-codex.json",
                timeout_seconds=120,
                parallel_tool_calls=True,
            ),
            "Codex LLM provider requires CodexLLMRequest",
        ),
        (
            BedrockLLMProviderDefinition(
                name="bedrock",
                models=(MODEL,),
                enabled=True,
                profile="claude-bedrock",
                timeout_seconds=120,
                max_output_tokens=4096,
            ),
            "Bedrock LLM provider requires BedrockLLMRequest",
        ),
    ],
)
def test_llm_model_manager_rejects_provider_request_mismatch(
    provider: LLMProviderDefinition,
    error: str,
) -> None:
    client_resolver = _FakeClientResolver(LLMResponse(ok=True, model=MODEL))
    manager = LLMModelManager(client_resolver=client_resolver)

    with pytest.raises(RuntimeError, match=error):
        manager.generate(provider=provider, request=_invalid_request())

    assert client_resolver.providers == []


def _request(*, model: LLMModelDefinition = MODEL) -> OpenAILLMRequest:
    return OpenAILLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=model,
        tool_choice=LLMToolChoiceMode.AUTO,
        parallel_tool_calls=True,
        temperature=0,
        max_tokens=4096,
        top_p=1,
    )


def _invalid_request() -> LLMRequest:
    return LLMRequest(messages=(LLMUserMessage("hello"),), model=MODEL)
