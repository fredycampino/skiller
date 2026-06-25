import pytest

from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.provider_registry import AgentFakeLLMModel
from skiller.domain.agent.llm.request import LLMRequest
from skiller.infrastructure.llm.defaults.fake_llm_port import FakeLLMPort

pytestmark = pytest.mark.unit


def test_fake_llm_returns_configured_text_payload() -> None:
    llm = FakeLLMPort(
        response_text='{"summary":"ok","severity":"low","next_action":"retry"}',
        model=AgentFakeLLMModel.MODEL1,
    )

    result = llm.generate(
        LLMRequest(
            messages=(),
            model=AgentFakeLLMModel.MODEL1,
        )
    )

    assert result == LLMResponse(
        ok=True,
        content='{"summary":"ok","severity":"low","next_action":"retry"}',
        model=AgentFakeLLMModel.MODEL1,
    )
