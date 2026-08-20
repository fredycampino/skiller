from __future__ import annotations

import asyncio
from dataclasses import dataclass

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.port.models_port import ModelsPort
from stui.usecase.normalize_command_use_case import Command, CommandKind
from stui.usecase.run_event_context import RunEventContext, RunStatus

_AUTH_FLOW_BY_ADAPTER = {
    "openai": "auths/openai",
    "codex": "auths/codex",
    "bedrock": "auths/bedrock",
}
_AUTH_FLOW_BY_PROVIDER = {
    "lmstudio": "auths/lmstudio",
}


@dataclass(frozen=True)
class AuthCommandResult:
    command: Command | None
    error_message: str = ""


@dataclass(frozen=True)
class AuthCommandUseCase:
    context: RunEventContext
    models_port: ModelsPort
    strings: TuiStrings = DEFAULT_TUI_STRINGS

    async def execute(self, *, command: Command) -> AuthCommandResult:
        if len(command.params) != 1:
            return AuthCommandResult(
                command=None,
                error_message=self.strings.auth_unknown_provider_message,
            )
        provider = command.params[0].lower()
        try:
            providers = await asyncio.to_thread(self.models_port.list_providers)
        except RuntimeError as exc:
            return AuthCommandResult(
                command=None,
                error_message=self.strings.auth_providers_query_failed_message.format(
                    message=str(exc).strip() or "unknown error"
                ),
            )
        item = next((item for item in providers if item.name == provider), None)
        if item is None:
            return AuthCommandResult(
                command=None,
                error_message=self.strings.auth_unknown_provider_message,
            )

        run_args = _auth_run_args(adapter=item.adapter, provider=provider)
        if run_args is None:
            return AuthCommandResult(
                command=None,
                error_message=self.strings.auth_unknown_provider_message,
            )
        return AuthCommandResult(
            command=self._run_command(command, run_args),
        )

    def _run_command(self, command: Command, run_args: str) -> Command:
        continue_id = _continue_id(self.context)
        if continue_id:
            run_args = f"{run_args} --arg continue_id={continue_id}"
        return Command(
            kind=CommandKind.RUN,
            name="/run",
            raw_text=command.raw_text,
            params=(run_args,),
            args_text=run_args,
        )


def _auth_run_args(*, adapter: str, provider: str) -> str | None:
    provider_flow = _AUTH_FLOW_BY_PROVIDER.get(provider)
    if provider_flow is not None:
        return provider_flow

    adapter_flow = _AUTH_FLOW_BY_ADAPTER.get(adapter)
    if adapter_flow is None:
        return None
    if adapter == "openai":
        return f"{adapter_flow} --arg provider={provider}"
    return adapter_flow


def _continue_id(context: RunEventContext) -> str:
    if context.status not in {
        RunStatus.WAITING_INPUT,
        RunStatus.WAITING_WEBHOOK,
        RunStatus.WAITING_CHANNEL,
    }:
        return ""
    return context.run_id.strip()
