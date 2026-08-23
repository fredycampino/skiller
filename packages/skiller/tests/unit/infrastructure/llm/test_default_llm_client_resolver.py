import pytest

from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import (
    BedrockLLMProviderDefinition,
    CodexLLMProviderDefinition,
    LLMApiKeySource,
    LLMApiKeySourceType,
    LLMModelDefinition,
    OpenAILLMProviderDefinition,
)
from skiller.infrastructure.llm.bedrock import converse_llm_port
from skiller.infrastructure.llm.bedrock.converse_llm_port import ConverseLLMPort
from skiller.infrastructure.llm.codex.codex_model_capabilities import (
    CodexResponsesProtocol,
)
from skiller.infrastructure.llm.codex.responses_llm_port import ResponsesLLMPort
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
        models=(
            LLMModelDefinition(
                model="kimi-k3", context_window_tokens=256_000, max_output_tokens=None
            ),
        ),
        enabled=True,
        base_url="https://api.moonshot.ai/v1",
        temperature=1,
        top_p=0.95,
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


def test_resolver_creates_codex_client_with_internal_lite_capabilities() -> None:
    provider = CodexLLMProviderDefinition(
        name="codex",
        timeout_seconds=120,
        models=(
            LLMModelDefinition(
                model="gpt-5.6-luna", context_window_tokens=1_050_000, max_output_tokens=None
            ),
        ),
        enabled=True,
        credentials_file="~/.skiller/secrets/openai-codex.json",
        parallel_tool_calls=True,
    )
    resolver = DefaultLLMClientResolver(
        api_key_datasource=OpenAIApiKeyDatasource(env={}),
    )

    client = resolver.resolve(provider)
    capabilities = client.request_mapper.capabilities_resolver.resolve("gpt-5.6-luna")

    assert isinstance(client, ResponsesLLMPort)
    assert capabilities.protocol == CodexResponsesProtocol.LITE
    assert client.credentials_file == provider.credentials_file
    assert client.timeout_seconds == 120


def test_resolver_creates_converse_client_for_bedrock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeClient:
        pass

    class _FakeSession:
        def __init__(self, *, profile_name: str) -> None:
            _ = profile_name

        def client(self, service_name: str, **kwargs: object) -> _FakeClient:
            _ = service_name
            _ = kwargs
            return _FakeClient()

    class _FakeConfig:
        def __init__(self, *, read_timeout: float) -> None:
            self.read_timeout = read_timeout

    monkeypatch.setattr(converse_llm_port, "_load_boto3_session_class", lambda: _FakeSession)
    monkeypatch.setattr(converse_llm_port, "_load_botocore_config_class", lambda: _FakeConfig)
    provider = BedrockLLMProviderDefinition(
        name="bedrock",
        timeout_seconds=45,
        models=(
            LLMModelDefinition(model="test", context_window_tokens=1_000, max_output_tokens=None),
        ),
        enabled=True,
        profile="bedrock-profile",
    )
    resolver = DefaultLLMClientResolver(
        api_key_datasource=OpenAIApiKeyDatasource(env={}),
    )

    client = resolver.resolve(provider)

    assert isinstance(client, ConverseLLMPort)
    assert client.profile == "bedrock-profile"
    assert client.timeout_seconds == 45
