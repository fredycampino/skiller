from __future__ import annotations

from dataclasses import dataclass

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.usecase.normalize_command_use_case import Command, CommandKind
from stui.usecase.run_event_context import RunEventContext, RunStatus

_AUTH_RUN_ARGS_BY_PROVIDER = {
    "": "auths/auth",
    "codex": "auths/codex",
    "minimax": "auths/minimax",
    "bedrock": "auths/bedrock",
}


@dataclass(frozen=True)
class AuthCommandResult:
    command: Command | None
    error_message: str = ""


@dataclass(frozen=True)
class AuthCommandUseCase:
    context: RunEventContext
    strings: TuiStrings = DEFAULT_TUI_STRINGS

    def execute(self, *, command: Command) -> AuthCommandResult:
        provider = _provider_name(command.params)
        if provider is None or provider not in _AUTH_RUN_ARGS_BY_PROVIDER:
            return AuthCommandResult(
                command=None,
                error_message=self.strings.auth_unknown_provider_message,
            )

        run_args = _AUTH_RUN_ARGS_BY_PROVIDER[provider]
        continue_id = _continue_id(self.context)
        if continue_id:
            run_args = f"{run_args} --arg continue_id={continue_id}"
        return AuthCommandResult(
            command=Command(
                kind=CommandKind.RUN,
                name="/run",
                raw_text=command.raw_text,
                params=(run_args,),
                args_text=run_args,
            )
        )


def _provider_name(params: tuple[str, ...]) -> str | None:
    if not params:
        return ""
    if len(params) != 1:
        return None
    return params[0].lower()


def _continue_id(context: RunEventContext) -> str:
    if context.status not in {
        RunStatus.WAITING_INPUT,
        RunStatus.WAITING_WEBHOOK,
        RunStatus.WAITING_CHANNEL,
    }:
        return ""
    return context.run_id.strip()
