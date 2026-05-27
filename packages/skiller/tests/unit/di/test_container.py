import pytest

from skiller.di.container import build_runtime_container
from skiller.di.llm_client_factory import LLMClientFactory
from skiller.domain.agent.agent_config_model import (
    AgentLLMProviderConfig,
    AgentLLMProviderType,
)
from skiller.infrastructure.config.settings_model import Settings
from skiller.infrastructure.llm import openai_llm
from skiller.infrastructure.llm.fake_llm import FakeLLM
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.llm.openai_codex_credentials import OpenAICodexCredentials
from skiller.infrastructure.llm.openai_codex_responses_llm import OpenAICodexResponsesLLM
from skiller.infrastructure.llm.openai_llm import OpenAILLM

pytestmark = pytest.mark.unit


class _FakeOpenAIClient:
    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        self.kwargs = kwargs


class _FakeCodexCredentialsLoader:
    def load(self, credentials_file: str) -> OpenAICodexCredentials:
        _ = credentials_file
        return OpenAICodexCredentials(access_token="codex-token", account_id="account-1")


@pytest.mark.parametrize(
    ("provider_type", "model", "expected_type"),
    [
        (AgentLLMProviderType.NULL, "null1", NullLLM),
        (AgentLLMProviderType.FAKE, "model1", FakeLLM),
        (AgentLLMProviderType.MINIMAX, "MiniMax-M2.7", OpenAILLM),
        (AgentLLMProviderType.CODEX, "gpt-5.5", OpenAICodexResponsesLLM),
    ],
)
def test_llm_client_factory_creates_expected_client(
    monkeypatch: pytest.MonkeyPatch,
    provider_type: AgentLLMProviderType,
    model: str,
    expected_type: type[object],
) -> None:
    monkeypatch.setattr(openai_llm, "_load_openai_client_class", lambda: _FakeOpenAIClient)
    monkeypatch.setattr(
        "skiller.infrastructure.llm.openai_codex_responses_llm.OpenAICodexCredentialsLoader",
        lambda: _FakeCodexCredentialsLoader(),
    )
    factory = LLMClientFactory()
    provider = _provider(provider_type=provider_type, model=model)

    client = factory.create(provider)

    assert isinstance(client, expected_type)


def test_build_runtime_container_does_not_load_agent_config_eagerly(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "runtime.db"),
    )

    build_runtime_container(settings=settings, skills_dir=str(tmp_path))


def _provider(
    *,
    provider_type: AgentLLMProviderType,
    model: str,
) -> AgentLLMProviderConfig:
    return AgentLLMProviderConfig(
        provider_type=provider_type,
        api_key="secret-key",
        model=model,
        timeout_seconds=30,
        context_window_tokens=100_000,
        credentials_file="/tmp/openai-codex.json",
    )
