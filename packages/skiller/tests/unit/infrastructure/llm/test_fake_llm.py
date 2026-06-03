import pytest

from skiller.domain.agent.agent_llm_provider_model import AgentFakeLLMModel
from skiller.domain.agent.llm_model import LLMResponse
from skiller.domain.agent.llm_request import LLMRequest
from skiller.infrastructure.llm.fake_llm import FakeLLM

pytestmark = pytest.mark.unit


def test_fake_llm_returns_configured_text_payload() -> None:
    llm = FakeLLM(
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
