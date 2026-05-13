import pytest

from skiller.application.agent.error_mapper import AgentErrorMapper
from skiller.domain.agent.llm_model import LLMResponse

pytestmark = pytest.mark.unit


def test_llm_request_includes_provider_error_and_code() -> None:
    message = AgentErrorMapper().llm_request(
        agent_id="support_agent",
        response=LLMResponse(ok=False, error="invalid params", error_code="2013"),
    )

    assert (
        message
        == "Agent 'support_agent' LLM request failed: invalid params (error_code=2013)"
    )


def test_llm_request_falls_back_to_finish_reason() -> None:
    message = AgentErrorMapper().llm_request(
        agent_id="support_agent",
        response=LLMResponse(ok=False, finish_reason="content_filter"),
    )

    assert message == "Agent 'support_agent' LLM request failed: finish_reason=content_filter"


def test_llm_request_falls_back_to_generic_detail() -> None:
    message = AgentErrorMapper().llm_request(
        agent_id="support_agent",
        response=LLMResponse(ok=False),
    )

    assert message == "Agent 'support_agent' LLM request failed: ok=false without error"
