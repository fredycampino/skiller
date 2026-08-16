import pytest

from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import (
    LLMApiKeySource,
    LLMApiKeySourceType,
    LLMModelDefinition,
    OpenAILLMProviderDefinition,
)
from skiller.infrastructure.llm.default_llm_client_resolver import DefaultLLMClientResolver
from skiller.infrastructure.llm.openai import openai_llm_port
from skiller.infrastructure.llm.openai.openai_api_key_datasource import (
    OpenAIApiKeyDatasource,
)
from skiller.infrastructure.llm.openai.openai_llm_port import OpenAILLMPort

pytestmark = pytest.mark.unit


class _FakeOpenAIClient:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


def test_resolver_creates_openai_client_from_provider_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(openai_llm_port, "_load_openai_client_class", lambda: _FakeOpenAIClient)
    provider = OpenAILLMProviderDefinition(
        name="moonshot",
        timeout_seconds=30,
        models=(LLMModelDefinition(model="kimi-k3", context_window_tokens=256_000),),
        enabled=True,
        base_url="https://api.moonshot.ai/v1",
        temperature=1,
        top_p=0.95,
        max_output_tokens=4096,
        parallel_tool_calls=True,
        tool_choice=LLMToolChoiceMode.AUTO,
        api_key_source=LLMApiKeySource(
            type=LLMApiKeySourceType.VALUE,
            value="secret",
        ),
        options={},
    )
    resolver = DefaultLLMClientResolver(
        api_key_datasource=OpenAIApiKeyDatasource(env={}),
    )

    client = resolver.resolve(provider)

    assert isinstance(client, OpenAILLMPort)
    assert client.base_url == provider.base_url
    assert client.api_key == "secret"
    assert client.timeout_seconds == 30
    assert client.mapper.extra_body is None
