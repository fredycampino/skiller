from __future__ import annotations

from dataclasses import dataclass

from skiller.interfaces.tui.viewmodel.console_screen_state import CompletionState


@dataclass(frozen=True)
class MoveCompletionUseCase:
    def execute(
        self,
        *,
        completion: CompletionState | None,
        delta: int,
    ) -> CompletionState | None:
        if completion is None or not completion.visible or not completion.items:
            return None

        selected_index = (completion.selected_index + delta) % len(completion.items)
        return CompletionState(
            visible=completion.visible,
            query=completion.query,
            items=completion.items,
            selected_index=selected_index,
            replace_from=completion.replace_from,
            replace_to=completion.replace_to,
        )
