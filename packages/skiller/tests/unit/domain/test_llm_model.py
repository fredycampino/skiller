import pytest

from skiller.domain.agent.llm_model import LLMResponse

pytestmark = pytest.mark.unit


def test_llm_response_normalizes_metadata_strings() -> None:
    response = LLMResponse(
        ok=False,
        content=" done ",
        model=" fake-model ",
        finish_reason=" stop ",
        error=" invalid params ",
        error_code=" 2013 ",
    )

    assert response.content == "done"
    assert response.model == "fake-model"
    assert response.finish_reason == "stop"
    assert response.error == "invalid params"
    assert response.error_code == "2013"


def test_llm_response_converts_empty_metadata_to_none() -> None:
    response = LLMResponse(
        ok=False,
        content=" \n ",
        model=" ",
        finish_reason="",
        error="\n",
        error_code="\t",
    )

    assert response.content is None
    assert response.model is None
    assert response.finish_reason is None
    assert response.error is None
    assert response.error_code is None


def test_llm_response_exposes_semantic_properties() -> None:
    response = LLMResponse(ok=False, content="done")

    assert response.has_text_content is True
    assert response.has_tool_calls is False
    assert response.is_error is True
