import pytest

from skiller.domain.agent.agent_llm_provider_model import AgentNullLLMModel
from skiller.domain.agent.llm_request import LLMRequest
from skiller.infrastructure.llm.defaults.null_llm_port import NullLLMPort

pytestmark = pytest.mark.unit


def test_null_llm_returns_configuration_error() -> None:
    llm = NullLLMPort()

    result = llm.generate(
        LLMRequest(
            messages=(),
            model=AgentNullLLMModel.NULL1,
        )
    )

    assert result.ok is False
    assert result.model == AgentNullLLMModel.NULL1
    assert result.error is not None
    assert "LLM is not configured" in result.error
