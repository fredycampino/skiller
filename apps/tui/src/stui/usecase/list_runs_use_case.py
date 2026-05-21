from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.runs_port import RunsPort
from stui.usecase.normalize_command_use_case import Command, CommandKind
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    UserInputItem,
    ViewStatusKind,
)


@dataclass(frozen=True)
class ListRunsResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class ListRunsUseCase:
    runs_port: RunsPort

    async def execute(
        self,
        *,
        state: ConsoleScreenState,
        command: Command,
        limit: int = 20,
    ) -> ListRunsResult:
        statuses = _resolve_runs_query(command)
        try:
            runs = await asyncio.to_thread(
                self.runs_port.list_runs,
                limit=limit,
                statuses=statuses,
            )
        except RuntimeError as exc:
            state.transcript.items.append(UserInputItem(text=command.raw_text))
            state.transcript.items.append(
                DispatchErrorItem(message=f"error: {str(exc).strip() or 'runs query failed'}")
            )
            state.set_status(kind=ViewStatusKind.ERROR, message="Error")
            state.set_runs_table()
            _reset_prompt(state, mode=PromptMode.DEFAULT)
            return ListRunsResult(state=state)

        state.transcript.items.append(UserInputItem(text=command.raw_text))
        state.set_runs_table(
            visible=True,
            command=command.raw_text,
            rows=runs,
        )
        state.set_status()
        _reset_prompt(state, mode=PromptMode.RUNS_TABLE)
        return ListRunsResult(state=state)


def _reset_prompt(state: ConsoleScreenState, *, mode: PromptMode) -> None:
    state.set_autocompletion()
    state.set_prompt(mode=mode)


def _resolve_runs_query(command: Command) -> list[str]:
    if command.kind != CommandKind.RUNS:
        return []

    if not command.params:
        return []

    statuses: list[str] = []
    parts = list(command.params)
    index = 0
    while index < len(parts):
        part = parts[index]
        if part == "--status" and index + 1 < len(parts):
            statuses.append(parts[index + 1])
            index += 2
            continue
        statuses.append(part)
        index += 1
    return statuses
