from __future__ import annotations

import pytest

from stui.usecase.refresh_agent_metrics_use_case import RefreshAgentMetricsUseCase
from stui.viewmodel.console_screen_state import (
    AgentMetricsState,
    AgentStepContext,
    AgentStepUsage,
    ConsoleScreenState,
)

pytestmark = pytest.mark.unit


def test_refresh_agent_metrics_updates_state() -> None:
    state = ConsoleScreenState()
    metrics = AgentMetricsState(
        usage=AgentStepUsage(
            estimated_system_tokens=None,
            prompt_tokens=3000,
            output_tokens=500,
            total_tokens=3500,
            cache_read_tokens=1800,
            cache_write_tokens=120,
            provider="codex",
            model="gpt-5",
        ),
        context=AgentStepContext(
            effective_window_tokens=100000,
            max_total_tokens_ratio=0.8,
            window_width_tokens=100000,
            model_context_window_tokens=100000,
        ),
    )

    result = RefreshAgentMetricsUseCase().execute(state=state, metrics=metrics)

    assert result.state.agent_metrics == metrics


def test_refresh_agent_metrics_clears_state() -> None:
    state = ConsoleScreenState()

    result = RefreshAgentMetricsUseCase().execute(state=state, metrics=None)

    assert result.state.agent_metrics is None
