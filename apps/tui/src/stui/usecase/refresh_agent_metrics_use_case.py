from __future__ import annotations

from dataclasses import dataclass

from stui.viewmodel.console_screen_state import AgentMetricsState, ConsoleScreenState


@dataclass(frozen=True)
class RefreshAgentMetricsResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class RefreshAgentMetricsUseCase:
    def execute(
        self,
        *,
        state: ConsoleScreenState,
        metrics: AgentMetricsState | None,
    ) -> RefreshAgentMetricsResult:
        state.set_agent_metrics(metrics)
        return RefreshAgentMetricsResult(state=state)
