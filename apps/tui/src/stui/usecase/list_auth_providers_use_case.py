from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.port.models_port import (
    MODEL_PROVIDER_SOURCE_NONE,
    ModelsPort,
    ModelsPortProviderItem,
)
from stui.usecase.auth_provider_catalog import auth_provider_names
from stui.usecase.normalize_command_use_case import Command
from stui.usecase.run_event_context import RunEventContext
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
    context: RunEventContext

    async def execute(
        self,
        *,
        state: ConsoleScreenState,
        command: Command,
    ) -> ListAuthProvidersResult:
        run_id = self.context.run_id.strip()
        if not run_id:
            return _auth_error(state=state, message="auth requires an active run")

        try:
            models = await asyncio.to_thread(self.models_port.list_models, run_id=run_id)
        except RuntimeError as exc:
            return _auth_error(
                state=state,
                message=str(exc).strip() or "auth providers query failed",
            )

        providers_by_name = {provider.name: provider for provider in models}
        providers = [
            providers_by_name.get(
                name,
                ModelsPortProviderItem(
                    name=name,
                    source=MODEL_PROVIDER_SOURCE_NONE,
                    models=(),
                ),
            )
            for name in auth_provider_names()
        ]
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
