import pytest

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.request import LLMRequest
from skiller.infrastructure.llm.defaults.null_llm_port import NullLLMPort

pytestmark = pytest.mark.unit


def _model(value: str, context_window_tokens: int) -> LLMModelDefinition:
    return LLMModelDefinition(
        model=value, context_window_tokens=context_window_tokens, max_output_tokens=None
    )


def test_null_llm_returns_configuration_error() -> None:
    llm = NullLLMPort()

    result = llm.generate(
        LLMRequest(
            messages=(),
            model=_model("null1", 100_000),
        )
    )

    assert result.model == _model("null1", 100_000)
    assert result.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert result.error_code == "provider_not_configured"
    assert result.error is not None
    assert "LLM is not configured" in result.error
