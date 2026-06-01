from __future__ import annotations

from dataclasses import dataclass

from stui.viewmodel.console_screen_state import (
    ActionOpenUrlItem,
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

        if not isinstance(action.action, ActionOpenUrlItem):
            state.set_notify_action()
            return ProjectNotifyActionResult(state=state)

        state.set_notify_action(
            NotifyActionState(
                run_id=action.run_id,
                step_id=action.step_id,
                message=action.action.message or "",
                action=action.action,
            )
        )
        return ProjectNotifyActionResult(state=state)


def _find_action(items: list[TranscriptItem]) -> StepNotifyActionItem | None:
    for item in reversed(items):
        if not isinstance(item, StepNotifyActionItem):
            continue
        return item
    return None


def _find_done(
    action: StepNotifyActionItem,
    items: list[TranscriptItem],
) -> NotifyActionDoneItem | None:
    for item in reversed(items):
        if not isinstance(item, NotifyActionDoneItem):
            continue
        if item.run_id != action.run_id:
            continue
        if item.step_id != action.step_id:
            continue
        if item.type != action.action.type:
            continue
        if (
            item.sequence is not None
            and action.sequence is not None
            and item.sequence < action.sequence
        ):
            continue
        return item
    return None
