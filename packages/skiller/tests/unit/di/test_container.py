import pytest

from skiller.di.container import _build_llm_model_manager, build_runtime_container
from skiller.domain.agent.agent_config_model import (
    AgentConfig,
    AgentLLMClientType,
    AgentLLMConfig,
    AgentLLMProviderConfig,
    AgentLLMProviderType,
)
from skiller.domain.agent.llm_model import LLMMessage, LLMRequest
from skiller.infrastructure.config.settings_model import Settings
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
def test_build_llm_model_manager_creates_expected_client_on_demand(
    monkeypatch: pytest.MonkeyPatch,
    provider: AgentLLMProviderType,
    client_type: AgentLLMClientType,
    expected_type: type[object],
) -> None:
    monkeypatch.setattr(openai_llm, "_load_openai_client_class", lambda: _FakeOpenAIClient)
    manager = _build_llm_model_manager()
    config = _config(provider=provider, client_type=client_type)
    request = LLMRequest(messages=(LLMMessage.user("hello"),))

    manager.generate(config=config, request=request)

    assert isinstance(manager.current_client, expected_type)


def test_build_runtime_container_does_not_load_agent_config_eagerly(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "runtime.db"),
    )

    build_runtime_container(settings=settings, skills_dir=str(tmp_path))


def _config(
    *,
    provider: AgentLLMProviderType,
    client_type: AgentLLMClientType,
) -> AgentConfig:
    return AgentConfig(
        llm=AgentLLMConfig(
            default_provider="test-provider",
            providers={
                "test-provider": AgentLLMProviderConfig(
                    provider=provider,
                    client_type=client_type,
                    api_key="secret-key",
                    base_url="https://api.example.com/v1",
                    model="test-model",
                    timeout_seconds=30,
                    context_window_tokens=100_000,
                )
            },
        )
    )
