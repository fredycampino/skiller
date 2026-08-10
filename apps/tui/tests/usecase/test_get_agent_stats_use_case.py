from __future__ import annotations

import asyncio

import pytest

from apps.tui.tests.support import FakeAgentPort, patched_to_thread
from stui.port.agent_port import (
    AgentContextStats,
    AgentContextWindowStats,
    AgentStatsResult,
    AgentStatsStatus,
)
from stui.usecase import get_agent_stats_use_case as module
from stui.usecase.get_agent_stats_use_case import GetAgentStatsUseCase
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus

pytestmark = pytest.mark.unit


def test_get_agent_stats_returns_context_stats() -> None:
    agent_port = FakeAgentPort(
        stats=AgentStatsResult(
            status=AgentStatsStatus.OK,
            run_id="run-1234",
            agent_id="agent-1",
            context=AgentContextStats(
                entries=10,
                estimated_tokens=1200,
                window=AgentContextWindowStats(
                    start_sequence=1,
                    end_sequence=10,
                    current_tokens=1200,
                    limit_tokens=80000,
                    capacity_tokens=100000,
                ),
            ),
        )
    )
    use_case = GetAgentStatsUseCase(agent_port=agent_port, context=_active_context())

    async def run() -> None:
        with patched_to_thread(module):
            result = await use_case.execute()

        assert result.stats is not None
        assert result.stats.window.current_tokens == 1200
        assert agent_port.stats_called_with == [("run-1234", "agent-1")]

    asyncio.run(run())


def test_get_agent_stats_returns_none_without_context_identifiers() -> None:
    agent_port = FakeAgentPort()
    use_case = GetAgentStatsUseCase(
        agent_port=agent_port,
        context=RunEventContext(
            run_id="",
            run_name="chat",
            mode=RunMode.CHAT,
            status=RunStatus.RUNNING,
            agent_id="",
        ),
    )

    result = asyncio.run(use_case.execute())

    assert result.stats is None
    assert agent_port.stats_called_with == []


@pytest.mark.parametrize(
    "status, context",
    [
        (AgentStatsStatus.AGENT_CONTEXT_NOT_READY, None),
        (AgentStatsStatus.OK, None),
    ],
)
def test_get_agent_stats_returns_none_when_stats_are_unavailable(
    status: AgentStatsStatus,
    context: AgentContextStats | None,
) -> None:
    use_case = GetAgentStatsUseCase(
        agent_port=FakeAgentPort(
            stats=AgentStatsResult(
                status=status,
                run_id="run-1234",
                agent_id="agent-1",
                context=context,
            )
        ),
        context=_active_context(),
    )

    async def run() -> None:
        with patched_to_thread(module):
            result = await use_case.execute()
        assert result.stats is None

    asyncio.run(run())


def _active_context() -> RunEventContext:
    return RunEventContext(
        run_id="run-1234",
        run_name="chat",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
        agent_id="agent-1",
    )

