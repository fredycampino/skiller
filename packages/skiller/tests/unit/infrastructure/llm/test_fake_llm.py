import pytest

from skiller.domain.agent.llm_model import LLMRequest, LLMResponse
from skiller.infrastructure.llm.fake_llm import FakeLLM

pytestmark = pytest.mark.unit


def test_fake_llm_returns_configured_text_payload() -> None:
    llm = FakeLLM(
        response_text='{"summary":"ok","severity":"low","next_action":"retry"}',
        model="fake-test",
    )

    result = llm.generate(LLMRequest(messages=(), model="model1"))

    assert result == LLMResponse(
        ok=True,
        content='{"summary":"ok","severity":"low","next_action":"retry"}',
        model="fake-test",
    )
