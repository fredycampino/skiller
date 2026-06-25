import base64
import json

import pytest

from skiller.di.container import build_runtime_container
from skiller.di.llm_client_factory import LLMClientFactory
from skiller.domain.agent.llm.provider_registry import (
    AgentBedrockLLMModel,
    AgentBedrockProvider,
    AgentCodexLLMModel,
    AgentCodexProvider,
    AgentFakeLLMModel,
    AgentFakeProvider,
    AgentLLMProvider,
    AgentLMStudioLLMModel,
    AgentLMStudioProvider,
    AgentMiniMaxLLMModel,
    AgentMiniMaxProvider,
    AgentNullLLMModel,
    AgentNullProvider,
)
from skiller.infrastructure.config.settings_model import Settings
from skiller.infrastructure.llm.bedrock import bedrock_llm_port
from skiller.infrastructure.llm.bedrock.bedrock_llm_port import BedrockLLMPort
from skiller.infrastructure.llm.codex.codex_credentials_datasource import CodexCredentials
from skiller.infrastructure.llm.codex.codex_llm_port import CodexLLMPort
from skiller.infrastructure.llm.defaults.fake_llm_port import FakeLLMPort
from skiller.infrastructure.llm.defaults.null_llm_port import NullLLMPort
from skiller.infrastructure.llm.openai import openai_llm_port
from skiller.infrastructure.llm.openai.openai_llm_port import OpenAILLMPort

pytestmark = pytest.mark.unit


class _FakeOpenAIClient:
    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        self.kwargs = kwargs


class _FakeCodexCredentialsDatasource:
    def load(self, credentials_file: str) -> CodexCredentials:
        _ = credentials_file
        return CodexCredentials(
            access_token=_token_with_account_id("account-1"),
            auth_mode="chatgpt",
            client_id="client-1",
            created_at=1,
            expires_at=3,
            expires_in=2,
            id_token="id-token",
            redirect_uri="http://localhost:1455/auth/callback",
            refresh_token="refresh-token",
            scope="openid profile email offline_access",
            source="skiller-openai-auth",
            token_type="bearer",
        )


class _FakeBedrockClient:
    def converse(self, **kwargs: object) -> dict[str, object]:
        _ = kwargs
        return {}


class _FakeBedrockSession:
    def __init__(self, *, profile_name: str) -> None:
        _ = profile_name

    def client(self, service_name: str, **kwargs: object) -> _FakeBedrockClient:
        _ = service_name
        _ = kwargs
        return _FakeBedrockClient()


class _FakeBedrockConfig:
    def __init__(self, *, read_timeout: float) -> None:
        _ = read_timeout


@pytest.mark.parametrize(
    ("provider", "expected_type"),
    [
        (
            AgentNullProvider(
                model=AgentNullLLMModel.NULL1,
                timeout_seconds=30,
                window_width_tokens=100_000,
            ),
            NullLLMPort,
        ),
        (
            AgentFakeProvider(
                model=AgentFakeLLMModel.MODEL1,
                timeout_seconds=30,
                window_width_tokens=100_000,
            ),
            FakeLLMPort,
        ),
        (
            AgentMiniMaxProvider(
                model=AgentMiniMaxLLMModel.M2_7,
                api_key="secret-key",
                timeout_seconds=30,
                window_width_tokens=100_000,
            ),
            OpenAILLMPort,
        ),
        (
            AgentLMStudioProvider(
                model=AgentLMStudioLLMModel.GEMMA_4_12B_QAT,
                timeout_seconds=30,
                window_width_tokens=131_072,
            ),
            OpenAILLMPort,
        ),
        (
            AgentCodexProvider(
                model=AgentCodexLLMModel.GPT_5_5,
                credentials_file="/tmp/openai-codex.json",
                timeout_seconds=30,
                window_width_tokens=100_000,
            ),
            CodexLLMPort,
        ),
        (
            AgentBedrockProvider(
                model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
                profile="claude-bedrock",
                timeout_seconds=30,
                window_width_tokens=100_000,
            ),
            BedrockLLMPort,
        ),
    ],
)
def test_llm_client_factory_creates_expected_client(
    monkeypatch: pytest.MonkeyPatch,
    provider: AgentLLMProvider,
    expected_type: type[object],
) -> None:
    monkeypatch.setattr(openai_llm_port, "_load_openai_client_class", lambda: _FakeOpenAIClient)
    monkeypatch.setattr(bedrock_llm_port, "_load_boto3_session_class", lambda: _FakeBedrockSession)
    monkeypatch.setattr(
        bedrock_llm_port,
        "_load_botocore_config_class",
        lambda: _FakeBedrockConfig,
    )
    monkeypatch.setattr(
        "skiller.di.llm_client_factory.CodexCredentialsDatasource",
        lambda: _FakeCodexCredentialsDatasource(),
    )
    factory = LLMClientFactory()

    client = factory.resolve(provider)

    assert isinstance(client, expected_type)


def test_build_runtime_container_does_not_load_agent_config_eagerly(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "runtime.db"),
    )

    build_runtime_container(settings=settings, skills_dir=str(tmp_path))


def _token_with_account_id(account_id: str) -> str:
    payload = json.dumps(
        {
            "https://api.openai.com/auth": {
                "chatgpt_account_id": account_id,
            }
        }
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"header.{encoded}.signature"
