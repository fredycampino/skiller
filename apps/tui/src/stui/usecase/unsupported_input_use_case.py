from __future__ import annotations

from dataclasses import dataclass

from stui.di.strings import TuiStrings
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    InfoItem,
    PromptMode,
    UserInputItem,
    ViewStatusKind,
)


@dataclass(frozen=True)
class UnsupportedInputResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class UnsupportedInputUseCase:
    strings: TuiStrings

    def execute(
        self,
        *,
        state: ConsoleScreenState,
        text: str,
    ) -> UnsupportedInputResult:
        state.set_autocompletion()
        state.set_prompt(mode=PromptMode.DEFAULT)
        state.set_status(kind=ViewStatusKind.HIDDEN)
        state.transcript.items.append(UserInputItem(text=text))
        state.transcript.items.append(
            InfoItem(text=self.strings.unsupported_input_message)
        )
        return UnsupportedInputResult(state=state)
