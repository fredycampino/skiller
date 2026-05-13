from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from stui.port.event_models import LogEvent
from stui.port.event_port import LogEventsListener
from stui.usecase.autocomplete_use_case import AutocompleteUseCase
from stui.usecase.interrupt_agent_turn_use_case import (
    InterruptAgentTurnUseCase,
)
from stui.usecase.list_runs_use_case import ListRunsUseCase
from stui.usecase.log_event_reducer_use_case import (
    LogEventReducerUseCase,
)
from stui.usecase.move_completion_use_case import (
    MoveCompletionUseCase,
)
from stui.usecase.normalize_command_use_case import (
    CommandKind,
    NormalizeCommandUseCase,
)
from stui.usecase.project_transcript_use_case import (
    ProjectTranscriptUseCase,
)
from stui.usecase.prompt_enter_use_case import PromptEnterUseCase
from stui.usecase.run_command_use_case import RunCommandUseCase
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.usecase.select_runs_table_row_use_case import (
    SelectRunsTableRowUseCase,
)
from stui.usecase.submit_waiting_input_use_case import (
    SubmitWaitingInputUseCase,
)
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    InfoItem,
    PromptMode,
    TranscriptItem,
    TranscriptMode,
    UserInputItem,
    ViewStatusKind,
)


@dataclass
class ConsoleScreenViewModel(LogEventsListener):
    _autocomplete_use_case: AutocompleteUseCase = field(init=False, repr=False)
    _interrupt_agent_turn_use_case: InterruptAgentTurnUseCase = field(
        init=False,
        repr=False,
    )
    _move_completion_use_case: MoveCompletionUseCase = field(init=False, repr=False)
    _list_runs_use_case: ListRunsUseCase = field(init=False, repr=False)
    _normalize_command_use_case: NormalizeCommandUseCase = field(init=False, repr=False)
    _log_event_reducer_use_case: LogEventReducerUseCase = field(
        init=False,
        repr=False,
    )
    _prompt_enter_use_case: PromptEnterUseCase = field(init=False, repr=False)
    _project_transcript_use_case: ProjectTranscriptUseCase = field(
        init=False,
        repr=False,
    )
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
        interrupt_agent_turn_use_case: InterruptAgentTurnUseCase,
        move_completion_use_case: MoveCompletionUseCase,
        list_runs_use_case: ListRunsUseCase,
        normalize_command_use_case: NormalizeCommandUseCase,
        log_event_reducer_use_case: LogEventReducerUseCase,
        project_transcript_use_case: ProjectTranscriptUseCase,
        prompt_enter_use_case: PromptEnterUseCase,
        run_command_use_case: RunCommandUseCase,
        select_runs_table_row_use_case: SelectRunsTableRowUseCase,
        submit_waiting_input_use_case: SubmitWaitingInputUseCase,
    ) -> None:
        self._run_event_context = run_event_context
        self._autocomplete_use_case = autocomplete_use_case
        self._interrupt_agent_turn_use_case = interrupt_agent_turn_use_case
        self._move_completion_use_case = move_completion_use_case
        self._list_runs_use_case = list_runs_use_case
        self._normalize_command_use_case = normalize_command_use_case
        self._log_event_reducer_use_case = log_event_reducer_use_case
        self._project_transcript_use_case = project_transcript_use_case
        self._prompt_enter_use_case = prompt_enter_use_case
        self._run_command_use_case = run_command_use_case
        self._select_runs_table_row_use_case = select_runs_table_row_use_case
        self._submit_waiting_input_use_case = submit_waiting_input_use_case
        self.state = ConsoleScreenState(session_key=session_key)
        self._on_state = None

    async def submit(self, text: str) -> None:
        command = self._normalize_command_use_case.execute(text=text)
        if command.kind == CommandKind.EMPTY:
            self._clear_prompt_state()
            self._emit_state()
            return

        if command.kind in {CommandKind.RUNS, CommandKind.CHATS}:
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

        if command.kind in {CommandKind.RUN, CommandKind.CHAT}:
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
        self.state.transcript.items.append(UserInputItem(text=command.raw_text))
        self.state.transcript.items.append(
            InfoItem(text="Use /run <agent> to execute an agent.")
        )
        self.state.view_status.kind = ViewStatusKind.HIDDEN
        self.state.view_status.message = ""
        self.state.prompt.waiting_prompt = ""
        self.state.prompt.mode = PromptMode.DEFAULT
        self._emit_state()

    def prompt_change(self, *, text: str, cursor_position: int) -> None:
        self.state.prompt.text = text
        self.state.prompt.cursor_position = cursor_position
        self.state.set_autocompletion(
            self._autocomplete_use_case.execute(
                text=text,
                cursor_position=cursor_position,
            )
        )
        self.state.prompt.mode = self._resolve_prompt_mode()
        self._emit_state()

    def move_completion(self, delta: int) -> bool:
        completion = self._move_completion_use_case.execute(
            completion=self.state.autocompletion,
            delta=delta,
        )
        if completion is None:
            return False

        self.state.set_autocompletion(completion)
        self.state.prompt.mode = self._resolve_prompt_mode()
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
        self._sync_transcript_mode_from_context()
        if self._on_state is not None:
            self._on_state(self.state)

    def _clear_prompt_state(self) -> None:
        self.state.set_autocompletion()
        self.state.prompt.text = ""
        self.state.prompt.cursor_position = 0
        self.state.prompt.mode = self._resolve_prompt_mode()

    def _sync_transcript_mode_from_context(self) -> None:
        if self._run_event_context.mode == RunMode.CHAT:
            self.state.transcript.mode = TranscriptMode.CHAT
            return
        self.state.transcript.mode = TranscriptMode.FLOW

    def notify(self, events: list[LogEvent]) -> None:
        result = self._log_event_reducer_use_case.execute(
            state=self.state,
            events=events,
        )
        self.state = result.state
        self.state.prompt.mode = self._resolve_prompt_mode()
        self._emit_state()

    def show_runs_table(self) -> None:
        self.state.runs_table.visible = True
        self.state.prompt.mode = self._resolve_prompt_mode()
        self._emit_state()

    def select_runs_table_row(
        self,
        *,
        prompt_text: str,
        run_id: str,
        skill_name: str,
    ) -> None:
        result = self._select_runs_table_row_use_case.execute(
            self,
            state=self.state,
            prompt_text=prompt_text,
            run_id=run_id,
            skill_name=skill_name,
        )
        self.state = result.state
        self._emit_state()

    def hide_runs_table(self) -> None:
        self.state.runs_table.visible = False
        self.state.runs_table.command = ""
        self.state.prompt.mode = self._resolve_prompt_mode()
        self._emit_state()

    def visible_transcript_items(self) -> list[TranscriptItem]:
        self._sync_transcript_mode_from_context()
        return self._project_transcript_use_case.execute(state=self.state)

    async def interrupt_running_agent_turn(self) -> bool:
        if self._run_event_context.status != RunStatus.RUNNING:
            return False
        if self._run_event_context.mode != RunMode.CHAT:
            return False
        if not self._run_event_context.run_id.strip():
            return False
        if self.state.prompt.mode == PromptMode.INTERRUPT_PENDING:
            return False

        self.state.prompt.mode = PromptMode.INTERRUPT_PENDING
        self._emit_state()

        result = await self._interrupt_agent_turn_use_case.execute(
            state=self.state,
            run_id=self._run_event_context.run_id,
        )
        self.state = result.state
        if not result.interrupted:
            self.state.prompt.mode = self._resolve_prompt_mode()
        self._emit_state()
        return result.interrupted

    def _resolve_prompt_mode(self) -> PromptMode:
        if self.state.runs_table.visible:
            return PromptMode.RUNS_TABLE
        if self._should_keep_interrupt_pending():
            return PromptMode.INTERRUPT_PENDING
        if (
            self.state.autocompletion is not None
            and self.state.autocompletion.visible
            and bool(self.state.autocompletion.items)
        ):
            return PromptMode.AUTOCOMPLETION
        return PromptMode.DEFAULT

    def _should_keep_interrupt_pending(self) -> bool:
        return (
            self.state.prompt.mode == PromptMode.INTERRUPT_PENDING
            and self._run_event_context.status == RunStatus.RUNNING
            and self._run_event_context.mode == RunMode.CHAT
        )
