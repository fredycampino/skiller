from __future__ import annotations

from dataclasses import dataclass

from skiller.interfaces.tui.port.run_port import RunObserver, RunPort
from skiller.interfaces.tui.screen.runs_table_view import RunRowMode, RunRowStatus
from skiller.interfaces.tui.usecase.run_event_context import RunEventContext, RunStatus
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    PromptMode,
    ViewStatusKind,
)


@dataclass(frozen=True)
class SelectRunsTableRowResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class SelectRunsTableRowUseCase:
    run_port: RunPort
    context: RunEventContext

    def execute(
        self,
        observer: RunObserver,
        *,
        state: ConsoleScreenState,
        prompt_text: str,
        mode: RunRowMode,
        status: RunRowStatus,
        run_id: str,
        skill_name: str,
        is_exit: bool,
    ) -> SelectRunsTableRowResult:
        table_command = state.runs_table.command.strip() or prompt_text.strip()
        state.runs_table.visible = False
        state.runs_table.command = ""

        if is_exit:
            state.prompt.mode = PromptMode.FLOW
            return SelectRunsTableRowResult(state=state)

        normalized_run_id = run_id.strip()
        if (
            _is_chats_command(table_command)
            and mode == RunRowMode.CHAT
            and status == RunRowStatus.WAITING_INPUT
            and normalized_run_id
        ):
            current_run_id = observer.run_id.strip()
            if current_run_id:
                self.run_port.unsubscribe(observer)
            observer.run_id = normalized_run_id
            state.autocompletion = None
            state.prompt.text = ""
            state.prompt.cursor_position = 0
            state.prompt.waiting_prompt = ""
            state.prompt.mode = PromptMode.FLOW
            state.session_key = normalized_run_id
            state.view_status.kind = ViewStatusKind.RUNNING
            state.view_status.message = ""
            self.context.activate_run(
                normalized_run_id,
                skill_name=skill_name.strip() or normalized_run_id,
                status=RunStatus.RUNNING,
            )
            self.run_port.subscribe(observer)
            return SelectRunsTableRowResult(state=state)

        state.prompt.mode = PromptMode.FLOW
        return SelectRunsTableRowResult(state=state)


def _is_chats_command(command_text: str) -> bool:
    normalized = command_text.strip().lower()
    return normalized == "/chats" or normalized.startswith("/chats ")
