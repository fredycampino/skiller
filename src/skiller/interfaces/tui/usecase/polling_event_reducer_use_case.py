from __future__ import annotations

import json
from dataclasses import dataclass

from skiller.interfaces.tui.port.run_port import PollingEvent, PollingEventKind
from skiller.interfaces.tui.usecase.run_event_context import (
    RunEventContext,
    RunMode,
    RunStatus,
)
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentToolCallItem,
    AgentToolResultItem,
    ConsoleScreenState,
    InfoItem,
    OutputFormat,
    RunOutputItem,
    RunStatusItem,
    RunStepItem,
    ScreenStatus,
)


@dataclass(frozen=True)
class PollingEventReducerResult:
    state: ConsoleScreenState


@dataclass(frozen=True)
class PollingEventReducerUseCase:
    context: RunEventContext

    def execute(
        self,
        *,
        state: ConsoleScreenState,
        events: list[PollingEvent],
    ) -> PollingEventReducerResult:
        for event in events:
            self._remember_active_run(event)
            if event.kind == PollingEventKind.LOG:
                if self.context.remember_event_id(event.event_id or ""):
                    continue
                self._append_log_event(state=state, event=event)
                continue

            normalized_status = event.status.strip().lower()
            if normalized_status == "waiting":
                state.screen_status = ScreenStatus.WAITING
                if event.prompt.strip():
                    state.waiting_prompt = event.prompt.strip()
                self.context.status = (
                    RunStatus.WAITING_INPUT
                    if (
                        self.context.status == RunStatus.WAITING_INPUT
                        or self._is_waiting_input_context(state, event.run_id)
                    )
                    else RunStatus.WAITING
                )
                self._append_run_status(state=state, run_id=event.run_id, status="waiting")
                continue
            if normalized_status == "succeeded":
                state.screen_status = ScreenStatus.READY
                state.waiting_prompt = ""
                self.context.status = RunStatus.SUCCESS
                self._append_run_status(state=state, run_id=event.run_id, status="succeeded")
                continue
            if normalized_status in {"failed", "cancelled"}:
                state.screen_status = ScreenStatus.ERROR
                state.waiting_prompt = ""
                self.context.status = RunStatus.FAILED
                if not self._has_terminal_error_status(state, event.run_id):
                    self._append_run_status(
                        state=state,
                        run_id=event.run_id,
                        status="error",
                        message=normalized_status,
                    )
                continue
            if normalized_status in {"created", "running"}:
                state.screen_status = ScreenStatus.RUNNING
                state.waiting_prompt = ""
                self.context.status = RunStatus.RUNNING
                continue
            state.screen_status = ScreenStatus.READY
            state.waiting_prompt = ""
            self.context.status = None

        return PollingEventReducerResult(state=state)

    def _append_log_event(
        self,
        *,
        state: ConsoleScreenState,
        event: PollingEvent,
    ) -> None:
        if event.event_type in {"INPUT_RECEIVED", "RUN_RESUME"}:
            return
        if event.event_type == "RUN_CREATE":
            return
        if event.event_type == "AGENT_ASSISTANT_MESSAGE":
            self._activate_current_run(
                run_id=event.run_id,
                mode=RunMode.AGENT,
                status=RunStatus.RUNNING,
            )
            assistant_text = event.assistant_text.strip()
            if assistant_text:
                state.transcript_items.append(
                    AgentAssistantMessageItem(
                        run_id=event.run_id,
                        step_id=event.step,
                        message_type=event.message_type,
                        text=assistant_text,
                    )
                )
            return
        if event.event_type == "AGENT_TOOL_CALL":
            self._activate_current_run(
                run_id=event.run_id,
                mode=RunMode.AGENT,
                status=RunStatus.RUNNING,
            )
            command = event.command.strip()
            if command:
                state.transcript_items.append(
                    AgentToolCallItem(
                        run_id=event.run_id,
                        step_id=event.step,
                        tool=event.tool,
                        command=command,
                    )
                )
            return
        if event.event_type == "AGENT_TOOL_RESULT":
            self._activate_current_run(
                run_id=event.run_id,
                mode=RunMode.AGENT,
                status=RunStatus.RUNNING,
            )
            preview = _extract_agent_tool_result_preview(event.output)
            if preview:
                state.transcript_items.append(
                    AgentToolResultItem(
                        run_id=event.run_id,
                        tool=event.tool,
                        preview=preview,
                    )
                )
            return
        if event.event_type == "STEP_STARTED":
            self._activate_current_run(
                run_id=event.run_id,
                mode=_mode_for_step_type(event.step_type),
                status=RunStatus.RUNNING,
            )
            if self._is_duplicate_wait_step(state=state, event=event):
                return
            state.transcript_items.append(
                RunStepItem(
                    run_id=event.run_id,
                    step_id=event.step,
                    step_type=event.step_type,
                )
            )
            return
        if event.event_type == "STEP_SUCCESS":
            normalized_step_type = event.step_type.strip().lower()
            self.context.mode = _mode_for_step_type(event.step_type)
            if (
                normalized_step_type == "agent"
                and self._has_matching_agent_final_message(state=state, event=event)
            ):
                return
            if normalized_step_type == "wait_input" and self._is_input_received_output(event):
                return
            state.transcript_items.append(
                RunOutputItem(
                    run_id=event.run_id,
                    step_type=event.step_type,
                    output=event.output or "ok",
                    format=_resolve_output_format(event.step_type),
                )
            )
            return
        if event.event_type == "STEP_ERROR":
            state.waiting_prompt = ""
            self.context.mode = _mode_for_step_type(event.step_type)
            self.context.status = RunStatus.FAILED
            self._append_run_status(
                state=state,
                run_id=event.run_id,
                status="error",
                message=event.error or event.text or "step failed",
            )
            state.screen_status = ScreenStatus.ERROR
            return
        if event.event_type == "RUN_WAITING":
            normalized_step_type = event.step_type.strip().lower()
            in_wait_input_context = self._is_waiting_input_context(state, event.run_id)
            waiting_status = (
                RunStatus.WAITING_INPUT
                if _is_wait_step_type(normalized_step_type) or in_wait_input_context
                else RunStatus.WAITING
            )
            self._activate_current_run(
                run_id=event.run_id,
                mode=_mode_for_step_type(event.step_type),
                status=waiting_status,
            )

            if _is_wait_step_type(normalized_step_type) or in_wait_input_context:
                state.waiting_prompt = _extract_waiting_prompt(event)
                return

            if normalized_step_type == "wait_input" and self._is_input_received_output(event):
                return
            if event.output or event.text:
                state.transcript_items.append(
                    RunOutputItem(
                        run_id=event.run_id,
                        step_type=event.step_type,
                        output=event.output or event.text,
                        format=_resolve_output_format(event.step_type),
                    )
                )
            return
        if event.text and not event.event_type:
            state.transcript_items.append(InfoItem(text=event.text))

    def _remember_active_run(self, event: PollingEvent) -> None:
        normalized_run_id = event.run_id.strip()
        if not normalized_run_id:
            return
        self._activate_current_run(
            run_id=normalized_run_id,
            mode=self.context.mode,
            status=self.context.status,
        )

    def _activate_current_run(
        self,
        *,
        run_id: str,
        mode: RunMode,
        status: RunStatus | None,
    ) -> None:
        self.context.activate_run(
            run_id,
            skill_name=self.context.skill_name,
            mode=mode,
            status=status,
        )

    def _append_run_status(
        self,
        *,
        state: ConsoleScreenState,
        run_id: str,
        status: str,
        message: str = "",
    ) -> None:
        if self._is_duplicate_run_status(
            state=state,
            run_id=run_id,
            status=status,
            message=message,
        ):
            return
        state.transcript_items.append(
            RunStatusItem(
                run_id=run_id,
                status=status,
                message=message,
            )
        )

    def _has_terminal_error_status(self, state: ConsoleScreenState, run_id: str) -> bool:
        for item in reversed(state.transcript_items):
            if not isinstance(item, RunStatusItem):
                continue
            if item.run_id != run_id:
                continue
            return item.status == "error"
        return False

    def _is_duplicate_run_status(
        self,
        *,
        state: ConsoleScreenState,
        run_id: str,
        status: str,
        message: str,
    ) -> bool:
        if not state.transcript_items:
            return False
        last_item = state.transcript_items[-1]
        if not isinstance(last_item, RunStatusItem):
            return False
        return (
            last_item.run_id == run_id
            and last_item.status == status
            and last_item.message == message
        )

    def _is_waiting_input_context(self, state: ConsoleScreenState, run_id: str) -> bool:
        for item in reversed(state.transcript_items):
            if not isinstance(item, RunStepItem):
                continue
            if item.run_id != run_id:
                continue
            return item.step_type.strip().lower() == "wait_input"
        return False

    def _is_input_received_output(self, event: PollingEvent) -> bool:
        raw_output = (event.output or "").strip()
        raw_text = (event.text or "").strip()
        if "input received" in raw_output.lower():
            return True
        if "input received" in raw_text.lower():
            return True
        if not raw_output.startswith(("{", "[")):
            return False

        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            return False

        if isinstance(parsed, dict):
            text = str(parsed.get("text", "")).strip().lower()
            return text == "input received."
        return False

    def _is_duplicate_wait_step(self, *, state: ConsoleScreenState, event: PollingEvent) -> bool:
        normalized_step_type = event.step_type.strip().lower()
        if normalized_step_type != "wait_input":
            return False
        step_id = event.step.strip()
        if not step_id:
            return False
        for item in state.transcript_items:
            if not isinstance(item, RunStepItem):
                continue
            if item.run_id != event.run_id:
                continue
            if item.step_type.strip().lower() != normalized_step_type:
                continue
            if item.step_id.strip() != step_id:
                continue
            return True
        return False

    def _has_matching_agent_final_message(
        self,
        *,
        state: ConsoleScreenState,
        event: PollingEvent,
    ) -> bool:
        last_visible_item = _last_visible_item(state.transcript_items)
        if not isinstance(last_visible_item, AgentAssistantMessageItem):
            return False
        if last_visible_item.run_id != event.run_id:
            return False
        if last_visible_item.step_id != event.step:
            return False
        if last_visible_item.message_type.strip().lower() != "final":
            return False

        final_text = _extract_agent_output_text(event.output).strip()
        if not final_text:
            return False
        return last_visible_item.text.strip() == final_text


def _resolve_output_format(step_type: str) -> OutputFormat:
    normalized = step_type.strip().lower()
    if normalized == "agent":
        return OutputFormat.MARKDOWN
    if normalized == "shell":
        return OutputFormat.STRUCTURED
    return OutputFormat.SIMPLE


def _is_wait_step_type(step_type: str) -> bool:
    return step_type == "wait_input"


def _mode_for_step_type(step_type: str) -> RunMode:
    if step_type.strip().lower() == "agent":
        return RunMode.AGENT
    return RunMode.FLOW


def _extract_waiting_prompt(event: PollingEvent) -> str:
    raw_output = (event.output or "").strip()
    raw_text = (event.text or "").strip()
    if raw_output:
        if not raw_output.startswith(("{", "[")):
            return raw_output
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            return raw_output
        if isinstance(parsed, dict):
            text = parsed.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
            value = parsed.get("value")
            if isinstance(value, dict):
                prompt = value.get("prompt")
                if isinstance(prompt, str) and prompt.strip():
                    return prompt.strip()
    return raw_text


def _extract_agent_tool_result_preview(output: str) -> str:
    normalized = output.strip()
    if not normalized:
        return ""
    if not normalized.startswith(("{", "[")):
        return normalized
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        return normalized

    if isinstance(parsed, dict):
        text = parsed.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return normalized


def _extract_agent_output_text(output: str) -> str:
    normalized = (output or "").strip()
    if not normalized:
        return ""
    if not normalized.startswith(("{", "[")):
        return normalized
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        return normalized

    if isinstance(parsed, dict):
        text = parsed.get("text")
        if isinstance(text, str):
            return text
    return normalized


def _last_visible_item(items: list[object]) -> object | None:
    if not items:
        return None
    return items[-1]
