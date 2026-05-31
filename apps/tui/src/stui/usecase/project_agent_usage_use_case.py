from __future__ import annotations

from dataclasses import dataclass

from stui.viewmodel.console_screen_state import (
    AgentStepFinalOutputItem,
    AgentUsageState,
    ConsoleScreenState,
    TranscriptItem,
)


@dataclass(frozen=True)
class ProjectAgentUsageResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class ProjectAgentUsageUseCase:
    def execute(
        self,
        *,
        state: ConsoleScreenState,
    ) -> ProjectAgentUsageResult:
        state.set_agent_usage(_agent_usage_state(items=state.transcript.items))
        return ProjectAgentUsageResult(state=state)


def _agent_usage_state(
    *,
    items: list[TranscriptItem],
) -> AgentUsageState | None:
    for item in reversed(items):
        if not isinstance(item, AgentStepFinalOutputItem):
            continue
        if item.usage is None:
            continue
        if item.usage.model is None:
            continue
        if item.usage.total_tokens is None:
            continue
        return AgentUsageState(
            model=item.usage.model,
            total_tokens=item.usage.total_tokens,
        )
    return None
