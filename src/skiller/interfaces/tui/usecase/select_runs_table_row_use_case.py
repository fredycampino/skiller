from __future__ import annotations

from dataclasses import dataclass

from skiller.interfaces.tui.port.run_port import RunObserver, RunPort
from skiller.interfaces.tui.usecase.run_event_context import (
    RunEventContext,
    RunMode,
    RunStatus,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    ScreenStatus,
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
        status: str,
        run_id: str,
        skill_name: str,
        is_exit: bool,
    ) -> SelectRunsTableRowResult:
        table_command = state.runs_table_command.strip() or prompt_text.strip()
        state.runs_table_visible = False
        state.runs_table_command = ""

        if is_exit:
            return SelectRunsTableRowResult(state=state)

        normalized_status = status.strip().lower()
        normalized_run_id = run_id.strip()
        if (
            _is_agents_command(table_command)
            and normalized_status == "waiting-i"
            and normalized_run_id
        ):
            current_run_id = observer.run_id.strip()
            if current_run_id:
                self.run_port.unsubscribe(observer)
            observer.run_id = normalized_run_id
            state.autocompletion = None
            state.prompt_text = ""
            state.prompt_cursor_position = 0
            state.waiting_prompt = ""
            state.session_key = normalized_run_id
            state.screen_status = ScreenStatus.RUNNING
            self.context.activate_run(
                normalized_run_id,
                skill_name=skill_name.strip() or normalized_run_id,
                mode=RunMode.FLOW,
                status=RunStatus.RUNNING,
            )
            self.run_port.subscribe(observer)
            return SelectRunsTableRowResult(state=state)

        return SelectRunsTableRowResult(state=state)


def _is_agents_command(command_text: str) -> bool:
    normalized = command_text.strip().lower()
    return normalized == "/agents" or normalized.startswith("/agents ")
