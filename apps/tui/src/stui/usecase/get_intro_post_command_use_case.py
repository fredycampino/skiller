from __future__ import annotations

from dataclasses import dataclass

from stui.usecase.normalize_command_use_case import Command, CommandKind

INFO_INTRO_RUN_ARG = "info/info"


@dataclass(frozen=True)
class GetIntroPostCommandResult:
    command: Command


@dataclass(frozen=True)
class GetIntroPostCommandUseCase:
    def execute(self) -> GetIntroPostCommandResult:
        return GetIntroPostCommandResult(
            command=Command(
                kind=CommandKind.RUN,
                name="/run",
                raw_text=f"/run {INFO_INTRO_RUN_ARG}",
                args_text=INFO_INTRO_RUN_ARG,
            )
        )
