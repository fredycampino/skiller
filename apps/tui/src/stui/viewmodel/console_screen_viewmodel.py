from __future__ import annotations

import asyncio
from collections.abc import Callable

from stui.port.event_models import LogEvent
from stui.port.event_port import LogEventsListener
from stui.usecase.get_run_action_use_case import GetRunActionResult
from stui.usecase.normalize_command_use_case import (
    Command,
    CommandKind,
)
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_event import InspectRunContextEvent
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    PromptMode,
)
from stui.viewmodel.console_screen_use_cases import ConsoleScreenUseCases


class ConsoleScreenViewModel(LogEventsListener):
    def __init__(
        self,
        *,
        session_key: str,
        run_event_context: RunEventContext,
        use_cases: ConsoleScreenUseCases,
    ) -> None:
        self._run_event_context = run_event_context
        self._use_cases = use_cases
        self.state = ConsoleScreenState(session_key=session_key)
        self._on_state: Callable[[ConsoleScreenState], None] | None = None
        self._on_event: Callable[[InspectRunContextEvent], None] | None = None

    def bind_on_state(self, callback: Callable[[ConsoleScreenState], None]) -> None:
        self._on_state = callback
        self._emit_state()

    def bind_on_event(self, callback: Callable[[InspectRunContextEvent], None]) -> None:
        self._on_event = callback

    async def on_start(self) -> None:
        start_result = await self._use_cases.start_console.execute(self, state=self.state)
        self.state = start_result.state
        resumed = False
        if not start_result.started_auth:
            resume_result = self._use_cases.resume_console.execute(self, state=self.state)
            self.state = resume_result.state
            resumed = resume_result.resumed
        self._emit_state()
        if start_result.started_auth or resumed:
            self._schedule_refresh_agent_context_stats()
            self._schedule_refresh_footer_context()

    def notify(self, events: list[LogEvent]) -> None:
        result = self._use_cases.event_state.execute(
            self,
            state=self.state,
            events=events,
        )
        self._use_cases.agent_status.execute(
            context=self._run_event_context,
            events=events,
        )
        agent_usage_result = self._use_cases.agent_usage.execute(
            state=result.state,
        )
        notify_action_result = self._use_cases.notify_action.execute(
            state=agent_usage_result.state,
        )
        run_action_result = self._use_cases.get_run_action.execute(
            state=notify_action_result.state,
        )
        self.state = notify_action_result.state

        self._emit_state()
        self._schedule_refresh_agent_context_stats()
        self._schedule_refresh_footer_context()
        command = run_action_result.command
        if command is not None:
            asyncio.create_task(self._execute_run_action(command, run_action_result))

    def open_notify_action_link(
        self,
        *,
        run_id: str,
        action_uid: str,
        url: str,
    ) -> None:
        result = self._use_cases.open_notify_action.execute(
            state=self.state,
            run_id=run_id,
            action_uid=action_uid,
            url=url,
        )
        self.state = result.state
        self._emit_state()

    def done_notify_action(
        self,
        *,
        run_id: str,
        action_uid: str,
    ) -> None:
        result = self._use_cases.done_notify_action.execute(
            state=self.state,
            run_id=run_id,
            action_uid=action_uid,
        )
        self.state = result.state
        self._emit_state()

    def _schedule_refresh_agent_context_stats(self) -> None:
        if self.state.agent_context_stats is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._refresh_agent_context_stats())

    async def _refresh_agent_context_stats(self) -> None:
        result = await self._use_cases.refresh_agent_context_stats.execute(
            state=self.state,
        )
        self.state = result.state
        self._emit_state()

    def _schedule_refresh_footer_context(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._refresh_footer_context())

    async def _refresh_footer_context(self) -> None:
        result = await self._use_cases.refresh_footer_context.execute(
            state=self.state,
        )
        self.state = result.state
        self._emit_state()

    async def _execute_run_action(
        self,
        command: Command,
        run_action: GetRunActionResult,
    ) -> None:
        result = await self._use_cases.run_command.execute(
            self,
            state=self.state,
            command=command,
        )
        self.state = result.state

        if run_action.action_uid:
            result = self._use_cases.done_notify_action.execute(
                state=self.state,
                run_id=run_action.run_id,
                action_uid=run_action.action_uid,
            )
            self.state = result.state

        self._emit_state()

    async def submit(self, text: str) -> None:
        command = self._use_cases.normalize_command.execute(text=text)
        if command.kind == CommandKind.EMPTY:
            self._clear_prompt_state()
            self._emit_state()
            return

        if command.kind == CommandKind.RUNS:
            result = await self._use_cases.list_runs.execute(
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
            result = await self._use_cases.run_command.execute(
                self,
                state=self.state,
                command=command,
            )
            self.state = result.state
            self._emit_state()
            return

        if (
            command.kind in {CommandKind.FREE_TEXT, CommandKind.UNKNOWN}
            and self._run_event_context.status == RunStatus.WAITING_INPUT
            and self._run_event_context.run_id
        ):
            result = await self._use_cases.submit_waiting_input.execute(
                self,
                state=self.state,
                text=text,
            )
            self.state = result.state
            self._emit_state()
            return

        if (
            command.kind == CommandKind.FREE_TEXT
            and self._run_event_context.status == RunStatus.WAITING_WEBHOOK
        ):
            self._emit_state()
            return

        result = self._use_cases.unsupported_input.execute(
            state=self.state,
            text=command.raw_text,
        )
        self.state = result.state
        self._emit_state()

    def prompt_change(self, *, text: str, cursor_position: int) -> None:
        self.state.prompt.text = text
        self.state.prompt.cursor_position = cursor_position
        autocompletion = self._use_cases.autocomplete.execute(
            text=text,
            cursor_position=cursor_position,
        )
        self.state.set_autocompletion(autocompletion)
        if autocompletion is not None and autocompletion.visible:
            self.state.runs_table.visible = False
            self.state.runs_table.command = ""
            self.state.set_agent_context_stats()
        self.state.prompt.mode = self._resolve_prompt_mode()
        self._emit_state()

    def move_completion(self, delta: int) -> bool:
        completion = self._use_cases.move_completion.execute(
            completion=self.state.autocompletion,
            delta=delta,
        )
        if completion is None:
            return False

        self.state.set_autocompletion(completion)
        self.state.prompt.mode = self._resolve_prompt_mode()
        self._emit_state()
        return True

    def screen_resized(self) -> None:
        self._emit_state()

    async def prompt_enter(self) -> None:
        result = self._use_cases.prompt_enter.execute(state=self.state)
        self.state = result.state
        if result.should_submit:
            await self.submit(result.submit_text)
            return

        self._emit_state()

    def inspect_run_context(self) -> None:
        if self._on_event is None:
            return

        self._on_event(
            InspectRunContextEvent(
                run_id=self._run_event_context.run_id,
                run_name=self._run_event_context.run_name,
                mode=self._run_event_context.mode,
                status=self._run_event_context.status,
                max_page=self._run_event_context.max_page,
            )
        )

    def get_max_page(self) -> int:
        return self._run_event_context.max_page

    def show_runs_table(self) -> None:
        self.state.runs_table.visible = True
        self.state.prompt.mode = self._resolve_prompt_mode()
        self._emit_state()

    def select_runs_table_row(
        self,
        *,
        prompt_text: str,
        run_id: str,
        run_name: str,
    ) -> None:
        result = self._use_cases.select_runs_table_row.execute(
            self,
            state=self.state,
            prompt_text=prompt_text,
            run_id=run_id,
            run_name=run_name,
        )
        self.state = result.state
        self._emit_state()

    def hide_runs_table(self) -> None:
        self.state.runs_table.visible = False
        self.state.runs_table.command = ""
        self.state.prompt.mode = self._resolve_prompt_mode()
        self._emit_state()

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

        result = await self._use_cases.interrupt_agent_turn.execute(
            state=self.state,
            run_id=self._run_event_context.run_id,
        )
        self.state = result.state
        if not result.interrupted:
            self.state.prompt.mode = self._resolve_prompt_mode()
        self._emit_state()
        return result.interrupted

    async def toggle_agent_stats(self) -> None:
        result = await self._use_cases.toggle_agent_stats.execute(
            state=self.state,
        )
        self.state = result.state
        self._emit_state()

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

    def _emit_state(self) -> None:
        if self._on_state is not None:
            self._on_state(self._build_screen_state())

    def _build_screen_state(self) -> ConsoleScreenState:
        state = ConsoleScreenState(
            session_key=self.state.session_key,
            run_name=self.state.run_name,
        )
        state.set_transcript(
            mode=self.state.transcript.mode,
            items=self._use_cases.transcript.execute(state=self.state),
        )
        state.set_prompt(
            text=self.state.prompt.text,
            cursor_position=self.state.prompt.cursor_position,
            waiting_prompt=self.state.prompt.waiting_prompt,
            mode=self.state.prompt.mode,
        )
        state.set_status(
            kind=self.state.view_status.kind,
            message=self.state.view_status.message,
        )
        state.set_runs_table(
            visible=self.state.runs_table.visible,
            command=self.state.runs_table.command,
            rows=self.state.runs_table.rows,
        )
        state.set_agent_usage(self.state.agent_usage)
        state.set_agent_context_stats(self.state.agent_context_stats)
        state.set_footer_context(self.state.footer_context)
        state.set_autocompletion(self.state.autocompletion)
        state.set_notify_action(self.state.notify_action)
        return state

    def _clear_prompt_state(self) -> None:
        self.state.set_autocompletion()
        self.state.prompt.text = ""
        self.state.prompt.cursor_position = 0
        self.state.prompt.mode = self._resolve_prompt_mode()
