from __future__ import annotations

import asyncio
from dataclasses import dataclass

from skiller.interfaces.tui.port.runs_port import RunsPort
from skiller.interfaces.tui.usecase.normalize_command_use_case import Command, CommandKind
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    ScreenStatus,
    UserInputItem,
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
        statuses, waiting_input_only = _resolve_runs_query(command)
        try:
            runs = await asyncio.to_thread(
                self.runs_port.list_runs,
                limit=limit,
                statuses=statuses,
            )
        except RuntimeError as exc:
            _clear_prompt_state(state)
            state.transcript_items.append(UserInputItem(text=command.raw_text))
            state.transcript_items.append(
                DispatchErrorItem(message=f"error: {str(exc).strip() or 'runs query failed'}")
            )
            state.screen_status = ScreenStatus.ERROR
            state.waiting_prompt = ""
            state.runs = tuple()
            state.runs_table_visible = False
            state.runs_table_command = ""
            return ListRunsResult(state=state)

        if waiting_input_only:
            runs = [run for run in runs if (run.wait_type or "").strip().lower() == "input"]

        _clear_prompt_state(state)
        state.transcript_items.append(UserInputItem(text=command.raw_text))
        state.runs = tuple(runs)
        state.runs_table_visible = True
        state.runs_table_command = command.raw_text
        state.screen_status = ScreenStatus.READY
        state.waiting_prompt = ""
        return ListRunsResult(state=state)


def _clear_prompt_state(state: ConsoleScreenState) -> None:
    state.autocompletion = None
    state.prompt_text = ""
    state.prompt_cursor_position = 0


def _resolve_runs_query(command: Command) -> tuple[list[str], bool]:
    if command.kind == CommandKind.AGENTS:
        return ["WAITING"], True

    if command.kind != CommandKind.RUNS:
        return [], False

    if not command.params:
        return [], False

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
    return statuses, False
