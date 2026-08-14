from __future__ import annotations

import pytest

from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMUsage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_registry import AgentFakeLLMModel
from skiller.domain.agent.llm.request import LLMRequest
from skiller.infrastructure.llm.mapper.llm_usage_mapper import (
    DefaultLLMUsageMapper,
    LLMProviderUsage,
)

pytestmark = pytest.mark.unit


def _request(*, system: str = "system", user: str = "user") -> LLMRequest:
    return LLMRequest(
        messages=(
            LLMSystemMessage(content=system),
            LLMUserMessage(content=user),
        ),
        model=AgentFakeLLMModel.MODEL1,
    )


def test_default_usage_mapper_maps_provider_usage_to_domain_usage() -> None:
    provider_usage = LLMProviderUsage(
        prompt_tokens=10,
        output_tokens=5,
        total_tokens=15,
        cache_read_tokens=8,
        cache_write_tokens=2,
    )

    usage = DefaultLLMUsageMapper().to_usage(
        provider_usage,
        request=_request(),
    )

    assert usage == LLMUsage(
        provider=None,
        model=None,
        prompt_tokens=10,
        estimated_system_tokens=6,
        output_tokens=5,
        total_tokens=15,
        cache_read_tokens=8,
        cache_write_tokens=2,
    )


def test_default_usage_mapper_preserves_missing_usage() -> None:
    assert DefaultLLMUsageMapper().to_usage(None, request=_request()) is None


def test_default_usage_mapper_preserves_unknown_system_token_estimate() -> None:
    provider_usage = LLMProviderUsage(
        prompt_tokens=None,
        output_tokens=5,
        total_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
    )

    usage = DefaultLLMUsageMapper().to_usage(
        provider_usage,
        request=_request(),
    )

    assert usage is not None
    assert usage.estimated_system_tokens is None


def test_default_usage_mapper_does_not_divide_by_zero_for_empty_messages() -> None:
    provider_usage = LLMProviderUsage(
        prompt_tokens=10,
        output_tokens=5,
        total_tokens=15,
        cache_read_tokens=None,
        cache_write_tokens=None,
    )

    usage = DefaultLLMUsageMapper().to_usage(
        provider_usage,
        request=LLMRequest(
            messages=(
                LLMAssistantMessage(
                    tool_calls=(
                        LLMToolCall(
                            id="call-1",
                            function=LLMToolCallFunction(
                                name="shell",
                                arguments_json='{"command":"pwd"}',
                            ),
                        ),
                    )
                ),
            ),
            model=AgentFakeLLMModel.MODEL1,
        ),
    )

    assert usage is not None
    assert usage.estimated_system_tokens is None
