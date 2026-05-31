from __future__ import annotations

import pytest

from stui.usecase.project_agent_usage_use_case import ProjectAgentUsageUseCase
from stui.viewmodel.console_screen_state import (
    AgentStepFinalOutputItem,
    AgentStepStopReason,
    AgentStepUsage,
    AgentUsageState,
    ConsoleScreenState,
    OutputFormat,
)

pytestmark = pytest.mark.unit


def test_project_agent_usage_from_latest_agent_step_final_output() -> None:
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
                completion_tokens=155,
                total_tokens=3155,
                provider="minimax",
                model="MiniMax-M2.5",
            ),
        )
    )

    result = ProjectAgentUsageUseCase().execute(state=state)

    assert result.state.agent_usage is not None
    assert result.state.agent_usage.model == "MiniMax-M2.5"
    assert result.state.agent_usage.total_tokens == 3155


def test_project_agent_usage_clears_when_agent_step_has_no_usage() -> None:
    state = ConsoleScreenState(
        agent_usage=AgentUsageState(model="MiniMax-M2.5", total_tokens=3155)
    )
    state.transcript.items.append(
        AgentStepFinalOutputItem(
            run_id="run-1234",
            step_id="support_agent",
            stop_reason=AgentStepStopReason.FINAL,
            final="Done",
            format=OutputFormat.MARKDOWN,
        )
    )

    result = ProjectAgentUsageUseCase().execute(state=state)

    assert result.state.agent_usage is None
