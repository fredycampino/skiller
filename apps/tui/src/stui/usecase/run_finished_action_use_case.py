from __future__ import annotations

from dataclasses import dataclass

from stui.usecase.normalize_command_use_case import Command, CommandKind
from stui.viewmodel.console_screen_state import (
    ActionRunItem,
    ConsoleScreenState,
    RunFinishedItem,
)


@dataclass(frozen=True)
class RunFinishedActionResult:
    command: Command | None


@dataclass(frozen=True)
class RunFinishedActionUseCase:
    def execute(self, *, state: ConsoleScreenState) -> RunFinishedActionResult:
        if not state.transcript.items:
            return RunFinishedActionResult(command=None)

        item = state.transcript.items[-1]
        if not isinstance(item, RunFinishedItem):
            return RunFinishedActionResult(command=None)
        if not isinstance(item.action, ActionRunItem):
            return RunFinishedActionResult(command=None)

        args_text = item.action.arg
        if item.action.params:
            args_text = f"{args_text} {item.action.params}"

        return RunFinishedActionResult(
            command=Command(
                kind=CommandKind.RUN,
                name="/run",
                raw_text=f"/run {args_text}",
                args_text=args_text,
            )
        )
