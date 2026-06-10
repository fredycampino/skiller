from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.agent_port import AgentPort, AgentStatsStatus
from stui.usecase.run_event_context import RunEventContext
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    FooterContextState,
)


@dataclass(frozen=True)
class RefreshFooterContextResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class RefreshFooterContextUseCase:
    agent_port: AgentPort
    context: RunEventContext

    async def execute(self, *, state: ConsoleScreenState) -> RefreshFooterContextResult:
        if state.agent_usage is None:
            state.set_footer_context()
            return RefreshFooterContextResult(state=state)
        if not self.context.run_id or not self.context.agent_id:
            state.set_footer_context()
            return RefreshFooterContextResult(state=state)

        result = await asyncio.to_thread(
            self.agent_port.stats,
            run_id=self.context.run_id,
            agent_id=self.context.agent_id,
        )
        if result.status != AgentStatsStatus.OK:
            state.set_footer_context()
            return RefreshFooterContextResult(state=state)
        if result.context is None:
            state.set_footer_context()
            return RefreshFooterContextResult(state=state)

        window = result.context.window
        state.set_footer_context(
            FooterContextState(
                model=state.agent_usage.model,
                current_tokens=window.current_tokens,
                limit_tokens=window.limit_tokens,
                capacity_tokens=window.capacity_tokens,
            )
        )
        return RefreshFooterContextResult(state=state)
