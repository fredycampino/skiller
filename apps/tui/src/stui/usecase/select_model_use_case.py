from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.models_port import ModelsPort
from stui.usecase.run_event_context import RunEventContext
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    ViewStatusKind,
)


@dataclass(frozen=True)
class SelectModelResult:
    state: ConsoleScreenState
    selected: bool


@dataclass(frozen=True)
class SelectModelUseCase:
    models_port: ModelsPort
    context: RunEventContext

    async def execute(
        self,
        *,
        state: ConsoleScreenState,
        provider: str,
        model: str,
    ) -> SelectModelResult:
        run_id = self.context.run_id
        if not run_id:
            return _selection_error(
                state=state,
                message="model selection requires an active run",
            )

        try:
            await asyncio.to_thread(
                self.models_port.select_model,
                run_id=run_id,
                provider=provider,
                model=model,
            )
            models = await asyncio.to_thread(self.models_port.list_models, run_id=run_id)
        except RuntimeError as exc:
            return _selection_error(
                state=state,
                message=str(exc).strip() or "model selection failed",
            )

        state.set_models_table(
            visible=True,
            command=state.models_table.command,
            rows=models,
        )
        state.set_status()
        state.set_autocompletion()
        state.set_prompt(mode=PromptMode.MODELS_TABLE)
        return SelectModelResult(state=state, selected=True)


def _selection_error(
    *,
    state: ConsoleScreenState,
    message: str,
) -> SelectModelResult:
    state.transcript.items.append(DispatchErrorItem(message=f"error: {message}"))
    state.set_status(kind=ViewStatusKind.ERROR, message="Error")
    state.set_autocompletion()
    if state.models_table.visible:
        state.prompt.mode = PromptMode.MODELS_TABLE
    else:
        state.prompt.mode = PromptMode.DEFAULT
    return SelectModelResult(state=state, selected=False)
