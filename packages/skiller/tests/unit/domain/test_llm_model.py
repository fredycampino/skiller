import pytest
from skiller.domain.agent.llm_model import LLMResponse

pytestmark = pytest.mark.unit


def test_llm_response_normalizes_metadata_strings() -> None:
    response = LLMResponse(
        ok=False,
        model=" fake-model ",
        finish_reason=" stop ",
        error=" invalid params ",
        error_code=" 2013 ",
    )

    assert response.model == "fake-model"
    assert response.finish_reason == "stop"
    assert response.error == "invalid params"
    assert response.error_code == "2013"


def test_llm_response_converts_empty_metadata_to_none() -> None:
    response = LLMResponse(
        ok=False,
        model=" ",
        finish_reason="",
        error="\n",
        error_code="\t",
    )

    assert response.model is None
    assert response.finish_reason is None
    assert response.error is None
    assert response.error_code is None
