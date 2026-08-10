from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.agent_port import AgentContextStats, AgentPort, AgentStatsStatus
from stui.usecase.run_event_context import RunEventContext


@dataclass(frozen=True)
class GetAgentStatsResult:
    stats: AgentContextStats | None


@dataclass(frozen=True)
class GetAgentStatsUseCase:
    agent_port: AgentPort
    context: RunEventContext

    async def execute(self) -> GetAgentStatsResult:
        if not self.context.run_id or not self.context.agent_id:
            return GetAgentStatsResult(stats=None)

        result = await asyncio.to_thread(
            self.agent_port.stats,
            run_id=self.context.run_id,
            agent_id=self.context.agent_id,
        )
        if result.status != AgentStatsStatus.OK:
            return GetAgentStatsResult(stats=None)

        return GetAgentStatsResult(stats=result.context)
