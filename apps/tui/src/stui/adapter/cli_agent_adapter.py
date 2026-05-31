from __future__ import annotations

from stui.adapter.agent_interrupt_mapper import AgentInterruptMapper
from stui.adapter.agent_stats_mapper import AgentStatsMapper
from stui.adapter.cli_invoker import CliInvoker
from stui.port.agent_port import (
    AgentPort,
    AgentStatsResult,
)
from stui.port.run_port import CommandAck


class CliAgentAdapter(AgentPort):
    def __init__(
        self,
        *,
        invoker: CliInvoker | None = None,
        interrupt_mapper: AgentInterruptMapper | None = None,
        stats_mapper: AgentStatsMapper | None = None,
    ) -> None:
        self.invoker = invoker or CliInvoker()
        self.interrupt_mapper = interrupt_mapper or AgentInterruptMapper()
        self.stats_mapper = stats_mapper or AgentStatsMapper()

    def interrupt(self, run_id: str) -> CommandAck:
        if not run_id:
            raise RuntimeError("agent interrupt command requires run_id")

        completed = self.invoker.run("agent", "interrupt", run_id)
        return self.interrupt_mapper.map(completed.stdout)

    def stats(self, *, run_id: str, agent_id: str) -> AgentStatsResult:
        if not run_id or not agent_id:
            raise RuntimeError("agent stats command requires run_id and agent_id")

        completed = self.invoker.run(
            "agent",
            "stats",
            run_id,
            "--agent",
            agent_id,
        )
        return self.stats_mapper.map(completed.stdout)
