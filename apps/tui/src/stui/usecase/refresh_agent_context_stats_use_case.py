from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.agent_port import AgentPort, AgentStatsStatus
from stui.usecase.run_event_context import RunEventContext
from stui.viewmodel.console_screen_state import (
    AgentContextStatsState,
    ConsoleScreenState,
)


@dataclass(frozen=True)
class RefreshAgentContextStatsResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class RefreshAgentContextStatsUseCase:
    agent_port: AgentPort
    context: RunEventContext

    async def execute(
        self,
        *,
        state: ConsoleScreenState,
    ) -> RefreshAgentContextStatsResult:
        if state.agent_context_stats is None:
            return RefreshAgentContextStatsResult(state=state)

        if not self.context.run_id or not self.context.agent_id:
            state.set_agent_context_stats()
            return RefreshAgentContextStatsResult(state=state)

        result = await asyncio.to_thread(
            self.agent_port.stats,
            run_id=self.context.run_id,
            agent_id=self.context.agent_id,
        )
        if result.status != AgentStatsStatus.OK or result.context is None:
            state.set_agent_context_stats()
            return RefreshAgentContextStatsResult(state=state)

        state.set_agent_context_stats(
            AgentContextStatsState(
                entries=result.context.entries,
                estimated_tokens=result.context.estimated_tokens,
                start_sequence=result.context.window.start_sequence,
                end_sequence=result.context.window.end_sequence,
                current_tokens=result.context.window.current_tokens,
                limit_tokens=result.context.window.limit_tokens,
                capacity_tokens=result.context.window.capacity_tokens,
            )
        )
        return RefreshAgentContextStatsResult(state=state)
