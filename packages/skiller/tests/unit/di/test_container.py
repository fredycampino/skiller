import pytest

from skiller.di.container import _build_llm
from skiller.domain.agent.agent_config_model import (
    AgentConfig,
    AgentLLMClientType,
    AgentLLMConfig,
    AgentLLMProviderConfig,
    AgentLLMProviderType,
)
from skiller.infrastructure.llm import openai_llm
from skiller.infrastructure.llm.fake_llm import FakeLLM
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.llm.openai_llm import OpenAILLM

pytestmark = pytest.mark.unit


class _FakeOpenAIClient:
    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        self.kwargs = kwargs


@pytest.mark.parametrize(
    ("provider", "client_type", "expected_type"),
    [
        (AgentLLMProviderType.NULL, AgentLLMClientType.NULL, NullLLM),
        (AgentLLMProviderType.FAKE, AgentLLMClientType.FAKE, FakeLLM),
        (
            AgentLLMProviderType.MINIMAX,
            AgentLLMClientType.OPENAI_CHAT_COMPLETIONS,
            OpenAILLM,
        ),
        (
            AgentLLMProviderType.OPENAI,
            AgentLLMClientType.OPENAI_CHAT_COMPLETIONS,
            OpenAILLM,
        ),
    ],
)
def test_build_llm_returns_expected_provider(
    monkeypatch: pytest.MonkeyPatch,
    provider: AgentLLMProviderType,
    client_type: AgentLLMClientType,
    expected_type: type[object],
) -> None:
    monkeypatch.setattr(openai_llm, "_load_openai_client_class", lambda: _FakeOpenAIClient)

    llm = _build_llm(_FakeAgentConfigPort(provider=provider, client_type=client_type))

    assert isinstance(llm, expected_type)


def test_build_llm_rejects_unsupported_client_type() -> None:
    with pytest.raises(ValueError, match="Unsupported LLM client type='anthropic_messages'"):
        _build_llm(
            _FakeAgentConfigPort(
                provider=AgentLLMProviderType.ANTHROPIC,
                client_type=AgentLLMClientType.ANTHROPIC_MESSAGES,
            )
        )


class _FakeAgentConfigPort:
    def __init__(
        self,
        *,
        provider: AgentLLMProviderType,
        client_type: AgentLLMClientType,
    ) -> None:
        self.provider = provider
        self.client_type = client_type

    def get_config(self) -> AgentConfig:
        return AgentConfig(
            llm=AgentLLMConfig(
                default_provider="test-provider",
                providers={
                    "test-provider": AgentLLMProviderConfig(
                        provider=self.provider,
                        client_type=self.client_type,
                        api_key="secret-key",
                        base_url="https://api.example.com/v1",
                        model="test-model",
                        timeout_seconds=30,
                        context_window_tokens=100_000,
                    )
                },
            )
        )
