from __future__ import annotations

from dataclasses import dataclass

from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    NotifyActionDoneItem,
    RunOutputItem,
    RunResumeItem,
    RunStepItem,
    StepNotifyActionItem,
    StepNotifyOutputItem,
    StepOutputItem,
    StepShellOutputItem,
    TranscriptItem,
    TranscriptMode,
)


@dataclass(frozen=True)
class ProjectTranscriptUseCase:
    def execute(
        self,
        *,
        state: ConsoleScreenState,
    ) -> list[TranscriptItem]:
        visible_items: list[TranscriptItem] = []
        for item in state.transcript.items:
            if isinstance(item, (StepNotifyActionItem, NotifyActionDoneItem)):
                continue
            if (
                state.transcript.mode == TranscriptMode.CHAT
                and _should_hide_in_chat_mode(item)
            ):
                continue
            visible_items.append(item)
        return visible_items


def _should_hide_in_chat_mode(item: TranscriptItem) -> bool:
    if isinstance(item, RunResumeItem):
        return True
    if isinstance(
        item,
        (
            RunStepItem,
            RunOutputItem,
            StepNotifyOutputItem,
            StepOutputItem,
            StepShellOutputItem,
        ),
    ):
        return item.step_type.strip().lower() in {"switch", "when"}
    return False
