import pytest

from skiller.domain.agent.config.model import (
    AgentContextCompactionConfig,
    AgentContextConfig,
)
from skiller.domain.agent.context.model import AgentContextMetrics
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition

pytestmark = pytest.mark.unit


def test_agent_context_window_uses_smaller_model_limit() -> None:
    model = _lmstudio_model()
    context_larger_than_model = AgentContextConfig(
        window_width_tokens=200_000,
        compaction=AgentContextCompactionConfig(
            compaction_trigger_ratio=0.8,
            compaction_target_ratio=0.5,
            keep_last_blocks=5,
        ),
    )
    context_smaller_than_model = AgentContextConfig(
        window_width_tokens=100_000,
        compaction=AgentContextCompactionConfig(
            compaction_trigger_ratio=0.8,
            compaction_target_ratio=0.5,
            keep_last_blocks=5,
        ),
    )

    assert (
        context_larger_than_model.effective_context_tokens(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 131_072
    )
    assert (
        context_larger_than_model.compaction_trigger_tokens(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 104_857
    )
    assert (
        context_larger_than_model.compaction_target_tokens(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 65_536
    )
    assert (
        context_larger_than_model.tool_result_max_bytes(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 50_000
    )
    assert context_larger_than_model.metrics(
        model_context_window_tokens=model.model_context_window_tokens,
    ) == AgentContextMetrics(
        effective_window_tokens=131_072,
        max_total_tokens_ratio=0.8,
    )
    assert (
        context_smaller_than_model.effective_context_tokens(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 100_000
    )
    assert (
        context_smaller_than_model.compaction_trigger_tokens(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 80_000
    )
    assert (
        context_smaller_than_model.compaction_target_tokens(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 50_000
    )
    assert (
        context_smaller_than_model.tool_result_max_bytes(
            model_context_window_tokens=model.model_context_window_tokens,
        )
        == 40_000
    )
    assert context_smaller_than_model.metrics(
        model_context_window_tokens=model.model_context_window_tokens,
    ) == AgentContextMetrics(
        effective_window_tokens=100_000,
        max_total_tokens_ratio=0.8,
    )


def _lmstudio_model() -> LLMModelDefinition:
    return LLMModelDefinition(
        model="google/gemma-4-12b-qat",
        context_window_tokens=131_072,
    )
