from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.models_port import ModelsPort
from stui.usecase.normalize_command_use_case import Command
from stui.usecase.run_event_context import RunEventContext
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    ViewStatusKind,
)


@dataclass(frozen=True)
class ListModelsResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class ListModelsUseCase:
    models_port: ModelsPort
    context: RunEventContext

    async def execute(
        self,
        *,
        state: ConsoleScreenState,
        command: Command,
    ) -> ListModelsResult:
        run_id = self.context.run_id.strip()
        if not run_id:
            return _models_error(
                state=state,
                message="models requires an active run",
            )

        try:
            models = await asyncio.to_thread(self.models_port.list_models, run_id=run_id)
        except RuntimeError as exc:
            return _models_error(
                state=state,
                message=str(exc).strip() or "models query failed",
            )

        state.set_runs_table()
        state.set_models_table(
            visible=True,
            command=command.raw_text,
            rows=models,
        )
        _reset_prompt(state, mode=PromptMode.MODELS_TABLE)
        return ListModelsResult(state=state)


def _models_error(
    *,
    state: ConsoleScreenState,
    message: str,
) -> ListModelsResult:
    state.transcript.items.append(DispatchErrorItem(message=f"error: {message}"))
    state.set_status(kind=ViewStatusKind.ERROR, message="Error")
    state.set_models_table()
    _reset_prompt(state, mode=PromptMode.DEFAULT)
    return ListModelsResult(state=state)


def _reset_prompt(state: ConsoleScreenState, *, mode: PromptMode) -> None:
    state.set_autocompletion()
    state.set_prompt(mode=mode)
