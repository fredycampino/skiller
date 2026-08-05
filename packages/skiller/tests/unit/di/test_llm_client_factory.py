import pytest

from skiller.di.llm_client_factory import LLMClientFactory
from skiller.domain.agent.llm.provider_moonshot import (
    MOONSHOT_BASE_URL,
    MOONSHOT_MODELS,
    AgentMoonshotLLMModel,
    AgentMoonshotProvider,
)
from skiller.infrastructure.llm.openai.openai_llm_port import OpenAILLMPort

pytestmark = pytest.mark.unit


def test_resolve_moonshot_creates_openai_compatible_client() -> None:
    provider = AgentMoonshotProvider(
        model=AgentMoonshotLLMModel.KIMI_K3,
        models=MOONSHOT_MODELS,
        api_key="secret",
        timeout_seconds=30,
        window_width_tokens=256_000,
    )

    client = LLMClientFactory().resolve(provider)

    assert isinstance(client, OpenAILLMPort)
    assert client.base_url == MOONSHOT_BASE_URL
    assert client.api_key == "secret"
    assert client.timeout_seconds == 30
    assert client.mapper.extra_body is None
    assert provider.top_p == 0.95
    assert client.client is not None
