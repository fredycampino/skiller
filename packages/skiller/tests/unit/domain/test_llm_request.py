from dataclasses import dataclass

import pytest

from skiller.domain.agent.llm.model import LLMToolChoiceMode, LLMUserMessage
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.agent.llm.request import (
    LLMRequest,
    OpenAILLMRequest,
)

pytestmark = pytest.mark.unit


def _model(value: str, context_window_tokens: int) -> LLMModelDefinition:
    return LLMModelDefinition(model=value, context_window_tokens=context_window_tokens)


@dataclass(frozen=True)
class _CustomModel:
    value: str
    model_context_window_tokens: int


@dataclass(frozen=True)
class _InvalidModelValue:
    value: int
    model_context_window_tokens: int


def test_llm_request_requires_supported_model() -> None:
    request = LLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=_model("model1", 100_000),
    )

    assert request.model == _model("model1", 100_000)

    with pytest.raises(TypeError, match="LLMRequest model must be an LLMModelLike"):
        LLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=object(),
        )


def test_llm_request_accepts_model_like_contract() -> None:
    model = _CustomModel(value="local/custom", model_context_window_tokens=4096)

    request = LLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=model,
    )

    assert request.model == model


def test_llm_request_rejects_invalid_model_like_values() -> None:
    with pytest.raises(TypeError, match="LLMRequest model value must be a non-empty string"):
        LLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=_InvalidModelValue(value=1, model_context_window_tokens=4096),
        )


def test_openai_llm_request_accepts_openai_compatible_model() -> None:
    request = OpenAILLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=_model("kimi-k3", 256_000),
        tool_choice=LLMToolChoiceMode.AUTO,
        parallel_tool_calls=True,
        temperature=1,
        max_tokens=4096,
        top_p=1,
    )

    assert request.model == _model("kimi-k3", 256_000)


def test_lmstudio_llm_request_accepts_model_like_contract() -> None:
    custom_model = _CustomModel(
        value="local/gemma-custom",
        model_context_window_tokens=10_000,
    )
    request = OpenAILLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=custom_model,
        tool_choice=LLMToolChoiceMode.AUTO,
        parallel_tool_calls=True,
        temperature=0.2,
        max_tokens=4096,
        top_p=1,
    )

    assert request.model == custom_model


def test_codex_llm_request_accepts_catalog_model_contract() -> None:
    model = _CustomModel(value="gpt-5.5", model_context_window_tokens=1_050_000)
    request = CodexLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=model,
        parallel_tool_calls=True,
        session_id="context-1",
    )

    assert request.model == model


def test_bedrock_llm_request_accepts_catalog_model_contract() -> None:
    model = _CustomModel(
        value="us.anthropic.claude-opus-4-6-v1",
        model_context_window_tokens=200_000,
    )
    request = BedrockLLMRequest(
        messages=(LLMUserMessage("hello"),),
        model=model,
        max_tokens=4096,
    )

    assert request.model == model
