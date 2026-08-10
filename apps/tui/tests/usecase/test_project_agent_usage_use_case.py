from __future__ import annotations

import pytest

from stui.usecase.project_agent_metrics_use_case import ProjectAgentMetricsUseCase
from stui.viewmodel.console_screen_state import (
    AgentStepFinalOutputItem,
    AgentStepStopReason,
    AgentStepUsage,
    ConsoleScreenState,
    OutputFormat,
)

pytestmark = pytest.mark.unit


def test_project_agent_metrics_from_latest_agent_step_final_output() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(
        AgentStepFinalOutputItem(
            run_id="run-1234",
            step_id="support_agent",
            stop_reason=AgentStepStopReason.FINAL,
            final="Done",
            format=OutputFormat.MARKDOWN,
            usage=AgentStepUsage(
                prompt_tokens=3000,
                output_tokens=155,
                total_tokens=3155,
                cache_read_tokens=2000,
                cache_write_tokens=None,
                provider="minimax",
                model="MiniMax-M2.5",
            ),
            context=None,
        )
    )

    metrics = ProjectAgentMetricsUseCase().execute(items=state.transcript.items)

    assert metrics is not None
    assert metrics.usage is not None
    assert metrics.usage.model == "MiniMax-M2.5"
    assert metrics.usage.prompt_tokens == 3000
    assert metrics.usage.total_tokens == 3155
    assert metrics.usage.cache_read_tokens == 2000
    assert metrics.context is None


def test_project_agent_metrics_clears_when_agent_step_has_no_metrics() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(
        AgentStepFinalOutputItem(
            run_id="run-1234",
            step_id="support_agent",
            stop_reason=AgentStepStopReason.FINAL,
            final="Done",
            usage=None,
            context=None,
            format=OutputFormat.MARKDOWN,
        )
    )

    metrics = ProjectAgentMetricsUseCase().execute(items=state.transcript.items)

    assert metrics is None
