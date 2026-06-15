from __future__ import annotations

from dataclasses import dataclass

from stui.viewmodel.console_screen_state import CompletionItem, ConsoleScreenState

_SUBMIT_COMPLETION_COMMANDS = frozenset({"/models", "/runs"})


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
            should_submit=_should_submit_completion(selected_item),
            submit_text=state.prompt.text,
        )


def _should_submit_completion(selected_item: CompletionItem) -> bool:
    insert_text = (selected_item.insert_text or "").strip()
    return selected_item.kind == "param" or insert_text in _SUBMIT_COMPLETION_COMMANDS
