from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from skiller.interfaces.tui.port.run_port import (
    EventObserver,
    ObserverType,
    PollingEvent,
)
from skiller.interfaces.tui.usecase.autocomplete_use_case import AutocompleteUseCase
from skiller.interfaces.tui.usecase.list_runs_use_case import ListRunsUseCase
from skiller.interfaces.tui.usecase.move_completion_use_case import (
    MoveCompletionUseCase,
)
from skiller.interfaces.tui.usecase.normalize_command_use_case import (
    CommandKind,
    NormalizeCommandUseCase,
)
from skiller.interfaces.tui.usecase.polling_event_reducer_use_case import (
    PollingEventReducerUseCase,
)
from skiller.interfaces.tui.usecase.prompt_enter_use_case import PromptEnterUseCase
from skiller.interfaces.tui.usecase.run_command_use_case import RunCommandUseCase
from skiller.interfaces.tui.usecase.run_event_context import RunEventContext, RunStatus
from skiller.interfaces.tui.usecase.select_runs_table_row_use_case import (
    SelectRunsTableRowUseCase,
)
from skiller.interfaces.tui.usecase.submit_waiting_input_use_case import (
    SubmitWaitingInputUseCase,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    InfoItem,
    ScreenStatus,
    UserInputItem,
)


@dataclass
class ConsoleScreenViewModel(EventObserver):
    type: Literal[ObserverType.RUN] = ObserverType.RUN
    run_id: str = ""
    _autocomplete_use_case: AutocompleteUseCase = field(init=False, repr=False)
    _move_completion_use_case: MoveCompletionUseCase = field(init=False, repr=False)
    _list_runs_use_case: ListRunsUseCase = field(init=False, repr=False)
    _normalize_command_use_case: NormalizeCommandUseCase = field(init=False, repr=False)
    _polling_event_reducer_use_case: PollingEventReducerUseCase = field(
        init=False,
        repr=False,
    )
    _prompt_enter_use_case: PromptEnterUseCase = field(init=False, repr=False)
    _run_command_use_case: RunCommandUseCase = field(init=False, repr=False)
    _submit_waiting_input_use_case: SubmitWaitingInputUseCase = field(
        init=False,
        repr=False,
    )
    _select_runs_table_row_use_case: SelectRunsTableRowUseCase = field(
        init=False,
        repr=False,
    )
    _run_event_context: RunEventContext = field(init=False, repr=False)
    state: ConsoleScreenState = field(init=False)
    _on_state: Callable[[ConsoleScreenState], None] | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def __init__(
        self,
        *,
        session_key: str,
        run_event_context: RunEventContext,
        autocomplete_use_case: AutocompleteUseCase,
        move_completion_use_case: MoveCompletionUseCase,
        list_runs_use_case: ListRunsUseCase,
        normalize_command_use_case: NormalizeCommandUseCase,
        polling_event_reducer_use_case: PollingEventReducerUseCase,
        prompt_enter_use_case: PromptEnterUseCase,
        run_command_use_case: RunCommandUseCase,
        select_runs_table_row_use_case: SelectRunsTableRowUseCase,
        submit_waiting_input_use_case: SubmitWaitingInputUseCase,
    ) -> None:
        self._run_event_context = run_event_context
        self._autocomplete_use_case = autocomplete_use_case
        self._move_completion_use_case = move_completion_use_case
        self._list_runs_use_case = list_runs_use_case
        self._normalize_command_use_case = normalize_command_use_case
        self._polling_event_reducer_use_case = polling_event_reducer_use_case
        self._prompt_enter_use_case = prompt_enter_use_case
        self._run_command_use_case = run_command_use_case
        self._select_runs_table_row_use_case = select_runs_table_row_use_case
        self._submit_waiting_input_use_case = submit_waiting_input_use_case
        self.state = ConsoleScreenState(session_key=session_key)
        self.run_id = ""
        self._on_state = None

    async def submit(self, text: str) -> None:
        command = self._normalize_command_use_case.execute(text=text)
        if command.kind == CommandKind.EMPTY:
            self._clear_prompt_state()
            self._emit_state()
            return

        if command.kind in {CommandKind.RUNS, CommandKind.AGENTS}:
            result = await self._list_runs_use_case.execute(
                state=self.state,
                command=command,
                limit=20,
            )
            self.state = result.state
            self._emit_state()
            return

        if command.kind == CommandKind.QUIT:
            self._clear_prompt_state()
            self._emit_state()
            return

        if command.kind == CommandKind.RUN:
            result = await self._run_command_use_case.execute(
                self,
                state=self.state,
                command=command,
            )
            self.state = result.state
            self._emit_state()
            return

        if (
            command.kind == CommandKind.FREE_TEXT
            and self._run_event_context.status == RunStatus.WAITING_INPUT
            and self._run_event_context.run_id
        ):
            result = await self._submit_waiting_input_use_case.execute(
                self,
                state=self.state,
                text=command.raw_text,
            )
            self.state = result.state
            self._emit_state()
            return

        self._clear_prompt_state()
        self.state.transcript_items.append(UserInputItem(text=command.raw_text))
        self.state.transcript_items.append(
            InfoItem(text="Use /run <skill> to execute a skill.")
        )
        self.state.screen_status = ScreenStatus.READY
        self.state.waiting_prompt = ""
        self._emit_state()

    def prompt_change(self, *, text: str, cursor_position: int) -> None:
        self.state.prompt_text = text
        self.state.prompt_cursor_position = cursor_position
        self.state.autocompletion = self._autocomplete_use_case.execute(
            text=text,
            cursor_position=cursor_position,
        )
        self._emit_state()

    def move_completion(self, delta: int) -> bool:
        completion = self._move_completion_use_case.execute(
            completion=self.state.autocompletion,
            delta=delta,
        )
        if completion is None:
            return False

        self.state.autocompletion = completion
        self._emit_state()
        return True

    async def prompt_enter(self) -> None:
        result = self._prompt_enter_use_case.execute(state=self.state)
        self.state = result.state
        if result.should_submit:
            await self.submit(result.submit_text)
            return

        self._emit_state()

    def bind_on_state(self, callback: Callable[[ConsoleScreenState], None]) -> None:
        self._on_state = callback

    def _emit_state(self) -> None:
        if self._on_state is not None:
            self._on_state(self.state)

    def _clear_prompt_state(self) -> None:
        self.state.autocompletion = None
        self.state.prompt_text = ""
        self.state.prompt_cursor_position = 0

    def notify(self, events: list[PollingEvent]) -> None:
        result = self._polling_event_reducer_use_case.execute(
            state=self.state,
            events=events,
        )
        self.state = result.state
        self._emit_state()

    def show_runs_table(self) -> None:
        self.state.runs_table_visible = True
        self._emit_state()

    def select_runs_table_row(
        self,
        *,
        prompt_text: str,
        status: str,
        run_id: str,
        skill_name: str,
        is_exit: bool,
    ) -> None:
        result = self._select_runs_table_row_use_case.execute(
            self,
            state=self.state,
            prompt_text=prompt_text,
            status=status,
            run_id=run_id,
            skill_name=skill_name,
            is_exit=is_exit,
        )
        self.state = result.state
        self._emit_state()

    def hide_runs_table(self) -> None:
        self.state.runs_table_visible = False
        self.state.runs_table_command = ""
        self._emit_state()
