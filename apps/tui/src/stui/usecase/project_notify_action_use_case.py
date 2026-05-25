from __future__ import annotations

from dataclasses import dataclass

from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    NotifyActionDoneItem,
    NotifyActionState,
    StepNotifyActionItem,
    TranscriptItem,
)


@dataclass(frozen=True)
class ProjectNotifyActionResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class ProjectNotifyActionUseCase:
    def execute(
        self,
        *,
        state: ConsoleScreenState,
    ) -> ProjectNotifyActionResult:
        action = _find_action(state.transcript.items)
        if action is None:
            state.set_notify_action()
            return ProjectNotifyActionResult(state=state)

        done = _find_done(action, state.transcript.items)
        if done is not None:
            state.set_notify_action()
            return ProjectNotifyActionResult(state=state)

        state.set_notify_action(
            NotifyActionState(
                run_id=action.run_id,
                step_id=action.step_id,
                message=action.message,
                label=action.label,
                url=action.url,
                status=action.status,
                auto_open=action.auto_open,
            )
        )
        return ProjectNotifyActionResult(state=state)


def _find_action(items: list[TranscriptItem]) -> StepNotifyActionItem | None:
    for item in reversed(items):
        if not isinstance(item, StepNotifyActionItem):
            continue
        if item.status == "pending":
            return item
    return None


def _find_done(
    action: StepNotifyActionItem,
    items: list[TranscriptItem],
) -> NotifyActionDoneItem | StepNotifyActionItem | None:
    for item in reversed(items):
        if not isinstance(item, (NotifyActionDoneItem, StepNotifyActionItem)):
            continue
        if item.run_id != action.run_id:
            continue
        if item.step_id != action.step_id:
            continue
        if isinstance(item, NotifyActionDoneItem):
            return item
        if item.status == "done":
            return item
    return None
