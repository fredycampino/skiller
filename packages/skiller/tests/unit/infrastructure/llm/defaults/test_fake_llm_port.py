import pytest

from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.request import LLMRequest
from skiller.infrastructure.llm.defaults.fake_llm_port import FakeLLMPort

pytestmark = pytest.mark.unit


def _model(value: str, context_window_tokens: int) -> LLMModelDefinition:
    return LLMModelDefinition(model=value, context_window_tokens=context_window_tokens)


def test_fake_llm_returns_configured_text_payload() -> None:
    llm = FakeLLMPort(
        response_text='{"summary":"ok","severity":"low","next_action":"retry"}',
        model=_model("model1", 100_000),
    )

    result = llm.generate(
        LLMRequest(
            messages=(),
            model=_model("model1", 100_000),
        )
    )

    assert result == LLMResponse(
        ok=True,
        content='{"summary":"ok","severity":"low","next_action":"retry"}',
        model=_model("model1", 100_000),
    )
