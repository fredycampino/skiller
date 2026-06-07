from __future__ import annotations

from dataclasses import dataclass

from stui.usecase.normalize_command_use_case import Command, CommandKind
from stui.usecase.run_event_context import RunEventContext
from stui.viewmodel.console_screen_state import (
    ActionRunItem,
    ConsoleScreenState,
    NotifyActionDoneItem,
    RunFinishedItem,
    StepNotifyActionItem,
)


@dataclass(frozen=True)
class GetRunActionResult:
    command: Command | None
    run_id: str = ""
    action_uid: str = ""


@dataclass(frozen=True)
class GetRunActionUseCase:
    context: RunEventContext

    def execute(self, *, state: ConsoleScreenState) -> GetRunActionResult:
        if not state.transcript.items:
            return GetRunActionResult(command=None)

        done_action_uids = {
            item.action_uid
            for item in state.transcript.items
            if isinstance(item, NotifyActionDoneItem)
        }
        self.context.actions_done.update(done_action_uids)

        last_item = state.transcript.items[-1]
        if not isinstance(last_item, (RunFinishedItem, StepNotifyActionItem)):
            return GetRunActionResult(command=None)

        items = [last_item]
        if isinstance(last_item, RunFinishedItem):
            items = list(reversed(state.transcript.items))

        for item in items:
            run_id = ""
            action_uid = ""
            action = None

            if isinstance(item, RunFinishedItem):
                action = item.action

            if isinstance(item, StepNotifyActionItem):
                action = item.action
                action_uid = item.action.uid
                run_id = item.run_id

            if not isinstance(action, ActionRunItem):
                continue

            if action.uid in self.context.actions_done:
                continue

            args_text = action.arg
            if action.params:
                args_text = f"{args_text} {action.params}"

            self.context.actions_done.add(action.uid)
            return GetRunActionResult(
                command=Command(
                    kind=CommandKind.RUN,
                    name="/run",
                    raw_text=f"/run {args_text}",
                    args_text=args_text,
                ),
                run_id=run_id,
                action_uid=action_uid,
            )

        return GetRunActionResult(command=None)
