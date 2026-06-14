from __future__ import annotations

from dataclasses import dataclass

from stui.viewmodel.console_screen_state import ConsoleScreenState


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

        replace_from = max(0, min(len(state.prompt.text), completion.replace_from))
        replace_to = max(replace_from, min(len(state.prompt.text), completion.replace_to))
        state.prompt.text = (
            state.prompt.text[:replace_from]
            + completion_text
            + state.prompt.text[replace_to:]
        )
        state.prompt.cursor_position = replace_from + len(completion_text)
        state.set_autocompletion()
        return PromptEnterResult(
            state=state,
            should_submit=selected_item.kind == "param",
            submit_text=state.prompt.text,
        )
