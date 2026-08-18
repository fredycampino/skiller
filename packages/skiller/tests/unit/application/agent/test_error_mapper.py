import pytest

from skiller.application.agent.mapper.error_mapper import AgentErrorMapper
from skiller.domain.agent.llm.model import LLMResponse, LLMUsage
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition

pytestmark = pytest.mark.unit


def _model(value: str, context_window_tokens: int) -> LLMModelDefinition:
    return LLMModelDefinition(model=value, context_window_tokens=context_window_tokens)


def test_llm_request_includes_provider_error_and_code() -> None:
    message = AgentErrorMapper().llm_request(
        agent_id="support_agent",
        response=LLMResponse(
            ok=False,
            model=_model("model1", 100_000),
            error="invalid params",
            error_code="2013",
        ),
    )

    assert message == "Agent 'support_agent' LLM request failed: invalid params (error_code=2013)"


def test_llm_request_falls_back_to_finish_reason() -> None:
    message = AgentErrorMapper().llm_request(
        agent_id="support_agent",
        response=LLMResponse(
            ok=False,
            model=_model("model1", 100_000),
            finish_reason="content_filter",
        ),
    )

    assert message == "Agent 'support_agent' LLM request failed: finish_reason=content_filter"


def test_llm_request_falls_back_to_generic_detail() -> None:
    message = AgentErrorMapper().llm_request(
        agent_id="support_agent",
        response=LLMResponse(ok=False, model=_model("model1", 100_000)),
    )

    assert (
        message
        == "Agent 'support_agent' LLM request failed: model=model1 returned ok=false without error"
    )


def test_invalid_final_message_embeds_response_json() -> None:
    message = AgentErrorMapper().invalid_final_message(
        agent_id="support_agent",
        response=LLMResponse(
            ok=True,
            model=_model("model1", 100_000),
            content=None,
            finish_reason="end_turn",
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
        '{"ok":true,"model":"model1","content":null,"tool_calls":[],'
        '"finish_reason":"end_turn",'
        '"usage":{"prompt_tokens":42688,"estimated_system_tokens":null,'
        '"output_tokens":2155,'
        '"total_tokens":44843,"cache_read_tokens":null,'
        '"cache_write_tokens":null,"provider":null,"model":null},'
        '"error":null,"error_code":null}'
    )
