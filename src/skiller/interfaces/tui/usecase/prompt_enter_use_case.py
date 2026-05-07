from __future__ import annotations

from dataclasses import dataclass

from skiller.interfaces.tui.viewmodel.console_screen_state import ConsoleScreenState


@dataclass(frozen=True)
class PromptEnterResult:
    state: ConsoleScreenState
    should_submit: bool
    submit_text: str = ""


@dataclass(frozen=True)
class PromptEnterUseCase:
    def execute(self, *, state: ConsoleScreenState) -> PromptEnterResult:
        completion = state.autocompletion
        if completion is None or not completion.visible or completion.selected_item is None:
            return PromptEnterResult(
                state=state,
                should_submit=True,
                submit_text=state.prompt.text,
            )

        selected_item = completion.selected_item
        completion_text = selected_item.insert_text or selected_item.label
        if not completion_text:
            completion_text = state.prompt.text[: state.prompt.cursor_position]
        completion_text = completion_text.rstrip() + " "

        state.prompt.text = completion_text
        state.prompt.cursor_position = len(completion_text)
        state.autocompletion = None
        return PromptEnterResult(state=state, should_submit=False)
