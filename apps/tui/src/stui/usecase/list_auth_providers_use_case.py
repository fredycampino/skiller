from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.models_port import ModelsPort
from stui.usecase.normalize_command_use_case import Command
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    ViewStatusKind,
)


@dataclass(frozen=True)
class ListAuthProvidersResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class ListAuthProvidersUseCase:
    models_port: ModelsPort

    async def execute(
        self,
        *,
        state: ConsoleScreenState,
        command: Command,
    ) -> ListAuthProvidersResult:
        try:
            providers = await asyncio.to_thread(self.models_port.list_providers)
        except RuntimeError as exc:
            return _auth_error(
                state=state,
                message=str(exc).strip() or "auth providers query failed",
            )

        state.set_runs_table()
        state.set_models_table()
        state.set_auth_table(
            visible=True,
            command=command.raw_text,
            rows=providers,
        )
        state.set_autocompletion()
        state.set_prompt(mode=PromptMode.AUTH_TABLE)
        return ListAuthProvidersResult(state=state)


def _auth_error(*, state: ConsoleScreenState, message: str) -> ListAuthProvidersResult:
    state.transcript.items.append(DispatchErrorItem(message=f"error: {message}"))
    state.set_status(kind=ViewStatusKind.ERROR, message="Error")
    state.set_runs_table()
    state.set_models_table()
    state.set_auth_table()
    state.set_autocompletion()
    state.set_prompt(mode=PromptMode.DEFAULT)
    return ListAuthProvidersResult(state=state)
