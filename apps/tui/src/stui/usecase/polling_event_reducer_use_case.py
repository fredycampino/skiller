from __future__ import annotations

import json
from dataclasses import dataclass

from stui.port.run_port import PollingEvent, PollingEventKind
from stui.usecase.run_event_context import RunEventContext, RunStatus
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentSystemNoticeItem,
    AgentToolCallItem,
    AgentToolResultItem,
    ConsoleScreenState,
    InfoItem,
    OutputFormat,
    PromptMode,
    RunOutputItem,
    RunStatusItem,
    RunStepItem,
    TranscriptMode,
    UserInputItem,
    ViewStatusKind,
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
                state.view_status.kind = ViewStatusKind.WAITING
                state.view_status.message = ""
                if event.prompt.strip():
                    state.prompt.waiting_prompt = event.prompt.strip()
                self.context.status = self._resolve_waiting_status(
                    state=state,
                    run_id=event.run_id,
                )
                self._append_run_status(state=state, run_id=event.run_id, status="waiting")
                continue
            if normalized_status == "succeeded":
                state.view_status.kind = ViewStatusKind.HIDDEN
                state.view_status.message = ""
                state.prompt.waiting_prompt = ""
                state.prompt.mode = PromptMode.FLOW
                self.context.status = RunStatus.SUCCESS
                self._append_run_status(state=state, run_id=event.run_id, status="succeeded")
                continue
            if normalized_status in {"failed", "cancelled"}:
                state.view_status.kind = ViewStatusKind.ERROR
                state.view_status.message = normalized_status
                state.prompt.waiting_prompt = ""
                state.prompt.mode = PromptMode.FLOW
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
                state.view_status.kind = ViewStatusKind.RUNNING
                state.view_status.message = ""
                state.prompt.waiting_prompt = ""
                self.context.status = RunStatus.RUNNING
                continue
            state.view_status.kind = ViewStatusKind.HIDDEN
            state.view_status.message = ""
            state.prompt.waiting_prompt = ""
            state.prompt.mode = PromptMode.FLOW
            self.context.status = None

        return PollingEventReducerResult(state=state)

    def _append_log_event(
        self,
        *,
        state: ConsoleScreenState,
        event: PollingEvent,
    ) -> None:
        if event.event_type == "INPUT_RECEIVED":
            user_input_text = event.user_input_text.strip()
            if user_input_text:
                state.transcript.items.append(UserInputItem(text=user_input_text))
            return
        if event.event_type == "RUN_RESUME":
            return
        if event.event_type == "RUN_CREATE":
            return
        if event.event_type == "AGENT_ASSISTANT_MESSAGE":
            self._activate_current_run(
                run_id=event.run_id,
                status=RunStatus.RUNNING,
            )
            state.transcript.mode = TranscriptMode.CHAT
            state.view_status.kind = ViewStatusKind.RUNNING
            state.view_status.message = ""
            if event.message_type.strip().lower() == "final":
                return
            assistant_text = event.assistant_text.strip()
            if assistant_text:
                state.transcript.items.append(
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
                status=RunStatus.RUNNING,
            )
            state.transcript.mode = TranscriptMode.CHAT
            state.view_status.kind = ViewStatusKind.RUNNING
            state.view_status.message = ""
            command = event.command.strip()
            if command:
                state.transcript.items.append(
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
                status=RunStatus.RUNNING,
            )
            state.transcript.mode = TranscriptMode.CHAT
            state.view_status.kind = ViewStatusKind.RUNNING
            state.view_status.message = ""
            preview = _extract_agent_tool_result_preview(event.output)
            if preview:
                state.transcript.items.append(
                    AgentToolResultItem(
                        run_id=event.run_id,
                        tool=event.tool,
                        preview=preview,
                    )
                )
            return
        if event.event_type in {"AGENT_INTERRUPTED", "AGENT_MAX_TURNS_EXHAUSTED"}:
            self._activate_current_run(
                run_id=event.run_id,
                status=RunStatus.RUNNING,
            )
            state.transcript.mode = TranscriptMode.CHAT
            state.view_status.kind = ViewStatusKind.RUNNING
            state.view_status.message = ""
            state.transcript.items.append(
                AgentSystemNoticeItem(
                    run_id=event.run_id,
                    step_id=event.step,
                    text=_resolve_agent_system_notice_text(event.event_type),
                )
            )
            return
        if event.event_type == "STEP_STARTED":
            self._activate_current_run(
                run_id=event.run_id,
                status=RunStatus.RUNNING,
            )
            self._update_modes_for_step_start(state=state, step_type=event.step_type)
            state.view_status.kind = ViewStatusKind.RUNNING
            state.view_status.message = ""
            if self._is_duplicate_wait_step(state=state, event=event):
                return
            state.transcript.items.append(
                RunStepItem(
                    run_id=event.run_id,
                    step_id=event.step,
                    step_type=event.step_type,
                )
            )
            return
        if event.event_type == "STEP_SUCCESS":
            normalized_step_type = event.step_type.strip().lower()
            self._update_modes_for_step_success(state=state, step_type=event.step_type)
            if (
                normalized_step_type == "agent"
                and _extract_agent_output_stop_reason(event.output)
                in {"interrupted", "max_turns_exhausted"}
            ):
                return
            if normalized_step_type == "wait_input" and self._is_input_received_output(event):
                return
            state.transcript.items.append(
                RunOutputItem(
                    run_id=event.run_id,
                    step_type=event.step_type,
                    output=event.output or "ok",
                    format=_resolve_output_format(event.step_type),
                )
            )
            return
        if event.event_type == "STEP_ERROR":
            state.prompt.waiting_prompt = ""
            self._update_modes_for_step_success(state=state, step_type=event.step_type)
            state.prompt.mode = PromptMode.FLOW
            self.context.status = RunStatus.FAILED
            self._append_run_status(
                state=state,
                run_id=event.run_id,
                status="error",
                message=event.error or event.text or "step failed",
            )
            state.view_status.kind = ViewStatusKind.ERROR
            state.view_status.message = event.error or event.text or "step failed"
            return
        if event.event_type == "RUN_WAITING":
            normalized_step_type = event.step_type.strip().lower()
            in_wait_input_context = self._is_waiting_input_context(state, event.run_id)
            waiting_status = _resolve_waiting_status_for_step(
                normalized_step_type,
                in_wait_input_context=in_wait_input_context,
            )
            self._activate_current_run(
                run_id=event.run_id,
                status=waiting_status,
            )
            state.view_status.kind = ViewStatusKind.WAITING
            state.view_status.message = ""
            self._update_prompt_mode_for_waiting(state=state, waiting_status=waiting_status)

            if waiting_status == RunStatus.WAITING_INPUT:
                state.prompt.waiting_prompt = _extract_waiting_prompt(event)
                return

            if normalized_step_type == "wait_input" and self._is_input_received_output(event):
                return
            if event.output or event.text:
                state.transcript.items.append(
                    RunOutputItem(
                        run_id=event.run_id,
                        step_type=event.step_type,
                        output=event.output or event.text,
                        format=_resolve_output_format(event.step_type),
                    )
                )
            return
        if event.text and not event.event_type:
            state.transcript.items.append(InfoItem(text=event.text))

    def _remember_active_run(self, event: PollingEvent) -> None:
        normalized_run_id = event.run_id.strip()
        if not normalized_run_id:
            return
        self._activate_current_run(
            run_id=normalized_run_id,
            status=self.context.status,
        )

    def _activate_current_run(
        self,
        *,
        run_id: str,
        status: RunStatus | None,
    ) -> None:
        self.context.activate_run(
            run_id,
            skill_name=self.context.skill_name,
            status=status,
        )

    def _resolve_waiting_status(
        self,
        *,
        state: ConsoleScreenState,
        run_id: str,
    ) -> RunStatus:
        if self.context.status in {
            RunStatus.WAITING_INPUT,
            RunStatus.WAITING_WEBHOOK,
            RunStatus.WAITING_CHANNEL,
        }:
            return self.context.status
        return _resolve_waiting_status_for_step(
            _last_run_step_type(state=state, run_id=run_id),
            in_wait_input_context=self._is_waiting_input_context(state, run_id),
        )

    def _update_modes_for_step_start(
        self,
        *,
        state: ConsoleScreenState,
        step_type: str,
    ) -> None:
        normalized_step_type = step_type.strip().lower()
        if normalized_step_type == "agent":
            state.transcript.mode = TranscriptMode.CHAT
            return
        if normalized_step_type == "wait_input" and state.transcript.mode == TranscriptMode.CHAT:
            return
        state.transcript.mode = TranscriptMode.FLOW

    def _update_modes_for_step_success(
        self,
        *,
        state: ConsoleScreenState,
        step_type: str,
    ) -> None:
        normalized_step_type = step_type.strip().lower()
        if normalized_step_type == "agent":
            state.transcript.mode = TranscriptMode.CHAT
            return
        if normalized_step_type == "wait_input" and state.transcript.mode == TranscriptMode.CHAT:
            return
        state.transcript.mode = TranscriptMode.FLOW

    def _update_prompt_mode_for_waiting(
        self,
        *,
        state: ConsoleScreenState,
        waiting_status: RunStatus,
    ) -> None:
        if waiting_status == RunStatus.WAITING_INPUT:
            state.prompt.mode = PromptMode.CHAT
            return
        state.prompt.mode = PromptMode.FLOW

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
        state.transcript.items.append(
            RunStatusItem(
                run_id=run_id,
                status=status,
                message=message,
            )
        )

    def _has_terminal_error_status(self, state: ConsoleScreenState, run_id: str) -> bool:
        for item in reversed(state.transcript.items):
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
        if not state.transcript.items:
            return False
        last_item = state.transcript.items[-1]
        if not isinstance(last_item, RunStatusItem):
            return False
        return (
            last_item.run_id == run_id
            and last_item.status == status
            and last_item.message == message
        )

    def _is_waiting_input_context(self, state: ConsoleScreenState, run_id: str) -> bool:
        for item in reversed(state.transcript.items):
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
        for item in state.transcript.items:
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

def _resolve_output_format(step_type: str) -> OutputFormat:
    normalized = step_type.strip().lower()
    if normalized == "agent":
        return OutputFormat.MARKDOWN
    if normalized == "shell":
        return OutputFormat.STRUCTURED
    return OutputFormat.SIMPLE


def _resolve_waiting_status_for_step(
    step_type: str,
    *,
    in_wait_input_context: bool,
) -> RunStatus:
    normalized = step_type.strip().lower()
    if normalized == "wait_input" or in_wait_input_context:
        return RunStatus.WAITING_INPUT
    if normalized == "wait_webhook":
        return RunStatus.WAITING_WEBHOOK
    if normalized == "wait_channel":
        return RunStatus.WAITING_CHANNEL
    return RunStatus.WAITING_INPUT if in_wait_input_context else RunStatus.WAITING_WEBHOOK


def _last_run_step_type(state: ConsoleScreenState, run_id: str) -> str:
    for item in reversed(state.transcript.items):
        if not isinstance(item, RunStepItem):
            continue
        if item.run_id != run_id:
            continue
        return item.step_type
    return ""


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


def _extract_agent_output_stop_reason(output: str) -> str:
    normalized = (output or "").strip()
    if not normalized:
        return ""
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    value = parsed.get("value")
    if not isinstance(value, dict):
        return ""
    data = value.get("data")
    if not isinstance(data, dict):
        return ""
    stop_reason = data.get("stop_reason")
    if not isinstance(stop_reason, str):
        return ""
    return stop_reason.strip().lower()


def _resolve_agent_system_notice_text(event_type: str) -> str:
    normalized = event_type.strip().upper()
    if normalized == "AGENT_INTERRUPTED":
        return "Interrupted by user"
    if normalized == "AGENT_MAX_TURNS_EXHAUSTED":
        return "Turn limit reached"
    return "Agent notice"
