from __future__ import annotations

from dataclasses import dataclass

from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentMetricsState,
    AgentStepFinalOutputItem,
    TranscriptItem,
)


@dataclass(frozen=True)
class ProjectAgentMetricsUseCase:
    def execute(
        self,
        *,
        items: list[TranscriptItem],
    ) -> AgentMetricsState | None:
        return _agent_metrics(items=items)


def _agent_metrics(
    *,
    items: list[TranscriptItem],
) -> AgentMetricsState | None:
    for item in reversed(items):
        if not isinstance(
            item,
            (
                AgentAssistantMessageItem,
                AgentStepFinalOutputItem,
            ),
        ):
            continue
        if item.usage is None and item.context is None:
            continue
        return AgentMetricsState(
            usage=item.usage,
            context=item.context,
        )
    return None
