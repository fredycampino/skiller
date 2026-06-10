from __future__ import annotations

import pytest

from apps.tui.tests.support import FakeAgentPort, patched_to_thread
from stui.port.agent_port import (
    AgentContextStats,
    AgentContextWindowStats,
    AgentStatsResult,
    AgentStatsStatus,
)
from stui.usecase import refresh_footer_context_use_case as module
from stui.usecase.refresh_footer_context_use_case import RefreshFooterContextUseCase
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    AgentUsageState,
    ConsoleScreenState,
    FooterContextState,
)

pytestmark = pytest.mark.unit


def test_refresh_footer_context_sets_footer_context_without_setting_panel_stats() -> None:
    use_case = RefreshFooterContextUseCase(
        agent_port=FakeAgentPort(
            stats=AgentStatsResult(
                status=AgentStatsStatus.OK,
                run_id="run-1234",
                agent_id="agent-1",
                context=AgentContextStats(
                    entries=10,
                    estimated_tokens=59000,
                    window=AgentContextWindowStats(
                        start_sequence=1,
                        end_sequence=10,
                        current_tokens=59500,
                        limit_tokens=80000,
                        capacity_tokens=100000,
                    ),
                ),
            )
        ),
        context=RunEventContext(
            run_id="run-1234",
            run_name="chat",
            mode=RunMode.CHAT,
            status=RunStatus.RUNNING,
            agent_id="agent-1",
        ),
    )
    state = ConsoleScreenState(
        agent_usage=AgentUsageState(model="gpt-5.5", total_tokens=59500)
    )

    async def run() -> None:
        with patched_to_thread(module):
            result = await use_case.execute(state=state)

        assert result.state.agent_context_stats is None
        assert result.state.footer_context is not None
        assert result.state.footer_context.model == "gpt-5.5"
        assert result.state.footer_context.current_tokens == 59500
        assert result.state.footer_context.limit_tokens == 80000
        assert result.state.footer_context.capacity_tokens == 100000

    import asyncio

    asyncio.run(run())


def test_refresh_footer_context_clears_footer_context_without_usage() -> None:
    use_case = RefreshFooterContextUseCase(
        agent_port=FakeAgentPort(),
        context=RunEventContext(
            run_id="run-1234",
            run_name="chat",
            mode=RunMode.CHAT,
            status=RunStatus.RUNNING,
            agent_id="agent-1",
        ),
    )
    state = ConsoleScreenState()

    async def run() -> None:
        result = await use_case.execute(state=state)
        assert result.state.footer_context is None

    import asyncio

    asyncio.run(run())


def test_refresh_footer_context_clears_footer_context_when_stats_status_is_not_ok() -> None:
    use_case = RefreshFooterContextUseCase(
        agent_port=FakeAgentPort(
            stats=AgentStatsResult(
                status=AgentStatsStatus.AGENT_CONTEXT_NOT_READY,
                run_id="run-1234",
                agent_id="agent-1",
            )
        ),
        context=_active_agent_context(),
    )
    state = _state_with_existing_footer_context()

    async def run() -> None:
        with patched_to_thread(module):
            result = await use_case.execute(state=state)
        assert result.state.footer_context is None

    import asyncio

    asyncio.run(run())


def test_refresh_footer_context_clears_footer_context_when_stats_context_is_missing() -> None:
    use_case = RefreshFooterContextUseCase(
        agent_port=FakeAgentPort(
            stats=AgentStatsResult(
                status=AgentStatsStatus.OK,
                run_id="run-1234",
                agent_id="agent-1",
                context=None,
            )
        ),
        context=_active_agent_context(),
    )
    state = _state_with_existing_footer_context()

    async def run() -> None:
        with patched_to_thread(module):
            result = await use_case.execute(state=state)
        assert result.state.footer_context is None

    import asyncio

    asyncio.run(run())


def test_refresh_footer_context_clears_footer_context_without_run_id() -> None:
    use_case = RefreshFooterContextUseCase(
        agent_port=FakeAgentPort(),
        context=RunEventContext(
            run_id="",
            run_name="chat",
            mode=RunMode.CHAT,
            status=RunStatus.RUNNING,
            agent_id="agent-1",
        ),
    )
    state = _state_with_existing_footer_context()

    async def run() -> None:
        result = await use_case.execute(state=state)
        assert result.state.footer_context is None

    import asyncio

    asyncio.run(run())


def test_refresh_footer_context_clears_footer_context_without_agent_id() -> None:
    use_case = RefreshFooterContextUseCase(
        agent_port=FakeAgentPort(),
        context=RunEventContext(
            run_id="run-1234",
            run_name="chat",
            mode=RunMode.CHAT,
            status=RunStatus.RUNNING,
            agent_id="",
        ),
    )
    state = _state_with_existing_footer_context()

    async def run() -> None:
        result = await use_case.execute(state=state)
        assert result.state.footer_context is None

    import asyncio

    asyncio.run(run())


def _active_agent_context() -> RunEventContext:
    return RunEventContext(
        run_id="run-1234",
        run_name="chat",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
        agent_id="agent-1",
    )


def _state_with_existing_footer_context() -> ConsoleScreenState:
    return ConsoleScreenState(
        agent_usage=AgentUsageState(model="gpt-5.5", total_tokens=59500),
        footer_context=FooterContextState(
            model="gpt-5.5",
            current_tokens=59500,
            limit_tokens=80000,
            capacity_tokens=100000,
        ),
    )
