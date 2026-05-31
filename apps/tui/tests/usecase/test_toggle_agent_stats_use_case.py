from __future__ import annotations

import asyncio

import pytest

import stui.usecase.toggle_agent_stats_use_case as toggle_agent_stats_module
from apps.tui.tests.support import FakeAgentPort, patched_to_thread
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.usecase.toggle_agent_stats_use_case import (
    ToggleAgentStatsUseCase,
)
from stui.viewmodel.console_screen_state import ConsoleScreenState

pytestmark = pytest.mark.unit


def test_toggle_agent_stats_fetches_current_agent_stats() -> None:
    state = ConsoleScreenState()
    context = _context()
    agent_port = FakeAgentPort()

    async def run() -> None:
        with patched_to_thread(toggle_agent_stats_module):
            result = await ToggleAgentStatsUseCase(
                agent_port=agent_port,
                context=context,
            ).execute(state=state)

        assert agent_port.stats_called_with == [("run-1234", "support_agent")]
        assert result.state.agent_context_stats is not None
        assert result.state.agent_context_stats.current_tokens == 2618
        assert result.state.agent_context_stats.limit_tokens == 80000

    asyncio.run(run())


def test_toggle_agent_stats_clears_existing_stats() -> None:
    state = ConsoleScreenState()
    context = _context()
    agent_port = FakeAgentPort()

    async def run() -> None:
        with patched_to_thread(toggle_agent_stats_module):
            use_case = ToggleAgentStatsUseCase(
                agent_port=agent_port,
                context=context,
            )
            first = await use_case.execute(state=state)
            second = await use_case.execute(state=first.state)

        assert second.state.agent_context_stats is None
        assert agent_port.stats_called_with == [("run-1234", "support_agent")]

    asyncio.run(run())


def _context() -> RunEventContext:
    return RunEventContext(
        run_id="run-1234",
        run_name="demo",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
        agent_id="support_agent",
    )
