import pytest

from skiller.application.agent.mapper.error_mapper import AgentErrorMapper
from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMResponse, LLMUsage
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition

pytestmark = pytest.mark.unit


def _model(value: str, context_window_tokens: int) -> LLMModelDefinition:
    return LLMModelDefinition(
        model=value, context_window_tokens=context_window_tokens, max_output_tokens=None
    )


def test_llm_request_includes_provider_error_and_code() -> None:
    message = AgentErrorMapper().llm_request(
        agent_id="support_agent",
        response=LLMResponse(
            model=_model("model1", 100_000),
            finish_type=LLMFinishType.ERROR_REQUEST_FAILED,
            error="invalid params",
            error_code="2013",
        ),
    )

    assert message == "Agent 'support_agent' LLM request failed: invalid params (error_code=2013)"


def test_llm_request_falls_back_to_finish_type() -> None:
    message = AgentErrorMapper().llm_request(
        agent_id="support_agent",
        response=LLMResponse(
            model=_model("model1", 100_000),
            finish_type=LLMFinishType.INVALID_RESPONSE_CONTENT_FILTER,
        ),
    )

    assert message == (
        "Agent 'support_agent' LLM request failed: "
        "finish_type=invalid_response_content_filter"
    )


def test_llm_request_uses_finish_type_without_error_detail() -> None:
    message = AgentErrorMapper().llm_request(
        agent_id="support_agent",
        response=LLMResponse(
            model=_model("model1", 100_000),
            finish_type=LLMFinishType.ERROR_REQUEST_FAILED,
        ),
    )

    assert message == "Agent 'support_agent' LLM request failed: finish_type=error_request_failed"


def test_invalid_final_message_embeds_response_json() -> None:
    message = AgentErrorMapper().invalid_final_message(
        agent_id="support_agent",
        response=LLMResponse(
            model=_model("model1", 100_000),
            finish_type=LLMFinishType.ERROR_MISSING_CONTENT,
            content=None,
            usage=LLMUsage(
                estimated_system_tokens=None,
                cache_read_tokens=None,
                cache_write_tokens=None,
                provider=None,
                model=None,
                prompt_tokens=42688,
                output_tokens=2155,
                total_tokens=44843,
            ),
        ),
    )

    assert message == (
        "Agent step 'support_agent' returned no final answer: "
        '{"model":"model1","finish_type":"error_missing_content",'
        '"content":null,"tool_calls":[],'
        '"usage":{"prompt_tokens":42688,"estimated_system_tokens":null,'
        '"output_tokens":2155,'
        '"total_tokens":44843,"cache_read_tokens":null,'
        '"cache_write_tokens":null,"provider":null,"model":null},'
        '"error":null,"error_code":null}'
    )
