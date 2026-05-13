from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from skiller.application.agent.config.event_output_sanitizer import (
    AgentEventOutputSanitizer,
)
from skiller.application.agent.feedback import AgentRunnerFeedback
from skiller.application.agent.observer.runtime_event_emitter import (
    AgentRuntimeEventEmitter,
)
from skiller.application.agent.tools.tool_manager import (
    PreparedTool,
    ToolManager,
    ToolPrepareFailure,
)
from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.domain.agent.agent_context_model import AgentContextEntry
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.llm_model import LLMToolCall
from skiller.domain.run.steering_model import SteeringAgentInterrupt, SteeringAgentMessage
from skiller.domain.shared.steering_port import SteeringPort
from skiller.domain.tool.tool_contract import ProcessTool, ToolResult, ToolResultStatus
from skiller.domain.tool.tool_execution_model import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionResults,
    ToolExecutionStatus,
)
from skiller.domain.tool.tool_process_model import (
    ToolProcessInterrupt,
    ToolProcessInterruptSignal,
    ToolProcessWait,
    ToolProcessWaitStatus,
)
from skiller.domain.tool.tool_process_port import ToolProcessPort


class AgentToolExecution(ToolProcessInterruptSignal):
    def __init__(
        self,
        *,
        agent_context_store: AgentContextStorePort,
        steering: SteeringPort,
        tool_manager: ToolManager,
        process_runner: ToolProcessPort,
        feedback: AgentRunnerFeedback,
        event_output_sanitizer: AgentEventOutputSanitizer,
        event_emitter: AgentRuntimeEventEmitter,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.steering = steering
        self.tool_manager = tool_manager
        self.process_runner = process_runner
        self.feedback = feedback
        self.event_output_sanitizer = event_output_sanitizer
        self.event_emitter = event_emitter

    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResults:
        # No tool calls means the tool loop has nothing to execute.
        if not request.response.tool_calls:
            return ToolExecutionResults(items=[])

        state = _ToolExecutionState(request=request)
        limit_result = self._reject_if_tool_call_limit_exceeded(state)
        # Too many tool calls rejects the batch before executing any tool.
        if limit_result is not None:
            return limit_result

        state.parent_sequence = self._append_tool_call_assistant_message(request)

        for raw_tool_call in request.response.tool_calls:
            # User interrupt stops the current tool loop immediately.
            if self.is_interrupted(request.run_id):
                self._append_interrupt_feedback(state)
                state.add(
                    ToolExecutionResult(
                        tool_call_id=request.turn_id,
                        tool="agent",
                        status=ToolExecutionStatus.INTERRUPTED,
                    )
                )
                return state.finish()

            tool_call = self._prepare_tool_call(state, raw_tool_call)
            execution = _ToolCallExecution(state=state, tool_call=tool_call)
            # Invalid tool-call JSON is feedback for the agent, then continue.
            if not tool_call.is_valid:
                self._append_agent_feedback(
                    state,
                    suffix="tool-format",
                    text=self.feedback.invalid_tool_call_arguments(
                        step_id=execution.step_id,
                        tool_call=tool_call.raw,
                        error=tool_call.error,
                    ),
                )
                result = ToolExecutionResult(
                    tool_call_id=tool_call.id,
                    tool=tool_call.name,
                    status=ToolExecutionStatus.INVALID,
                )
                state.add(result)
                continue

            tool_call_entry = self._append_tool_call(execution)
            self._emit_tool_call(execution, tool_call_entry)

            prepare_result = self.tool_manager.prepare(
                AgentToolRequest(
                    run_id=request.run_id,
                    step_id=request.step_id,
                    context_id=request.context_id,
                    turn_id=request.turn_id,
                    tool_call_id=tool_call.id,
                    tool=tool_call.name,
                    args=tool_call.args,
                    allowed_tools=request.allowed_tools,
                )
            )
            # Process tools run through the managed process runner.
            if prepare_result.ok and isinstance(prepare_result.prepared.tool, ProcessTool):
                tool_result = self._execute_process_tool(
                    execution,
                    prepare_result.prepared,
                )
            # Direct tools run in-process through the tool manager.
            if prepare_result.ok and not isinstance(
                prepare_result.prepared.tool,
                ProcessTool,
            ):
                tool_result = self.tool_manager.execute_prepared(prepare_result.prepared)
            # Agent-correctable prepare failures are persisted as tool feedback.
            if prepare_result.error in {
                ToolPrepareFailure.REQUEST_INVALID,
                ToolPrepareFailure.POLICY_BLOCKED,
            }:
                tool_result = ToolResult(
                    name=prepare_result.tool_name,
                    status=ToolResultStatus.FAILED,
                    data={"error": prepare_result.error.value},
                    text=None,
                    error=prepare_result.error_message,
                )
            # Technical prepare failures terminate the agent step.
            if prepare_result.error in {
                ToolPrepareFailure.REQUEST_EXCEPTION,
                ToolPrepareFailure.POLICY_EXCEPTION,
            }:
                state.add(
                    ToolExecutionResult(
                        tool_call_id=tool_call.id,
                        tool=tool_call.name,
                        status=ToolExecutionStatus(prepare_result.error.value),
                        error_message=prepare_result.error_message,
                    )
                )
                return state.finish()

            # Terminal tool execution statuses stop the tool loop.
            if (
                isinstance(tool_result, ToolExecutionResult)
                and tool_result.status.is_terminal()
            ):
                state.add(tool_result)
                return state.finish()

            # Non-terminal tool execution statuses are recorded and skipped.
            if isinstance(tool_result, ToolExecutionResult):
                state.add(tool_result)
                continue

            # Process interruption records user feedback and stops the tool loop.
            if tool_result is None:
                self._append_interrupt_feedback(state)
                state.add(
                    ToolExecutionResult(
                        tool_call_id=request.turn_id,
                        tool="agent",
                        status=ToolExecutionStatus.INTERRUPTED,
                    )
                )
                return state.finish()

            tool_result_entry = self.agent_context_store.append_tool_result(
                scope=execution.request,
                turn_id=execution.turn_id,
                parent_sequence=execution.parent_sequence,
                tool_call_id=tool_call.id,
                result=tool_result,
            )
            self._emit_tool_result(execution, tool_result_entry, tool_result)
            state.add(
                ToolExecutionResult(
                    tool_call_id=tool_call.id,
                    tool=tool_result.name,
                    status=ToolExecutionStatus.EXECUTED,
                )
            )

        return state.finish()

    def _append_tool_call(
        self,
        execution: "_ToolCallExecution",
    ) -> AgentContextEntry:
        tool_call = execution.tool_call
        return self.agent_context_store.append_tool_call(
            scope=execution.request,
            turn_id=execution.turn_id,
            parent_sequence=execution.parent_sequence,
            tool_call_id=tool_call.id,
            tool=tool_call.name,
            args=tool_call.args,
        )

    def _emit_tool_call(
        self,
        execution: "_ToolCallExecution",
        entry: AgentContextEntry,
    ) -> None:
        tool_call = execution.tool_call
        self.event_emitter.emit_tool_call(
            run_id=execution.run_id,
            step_id=execution.step_id,
            turn_id=execution.turn_id,
            sequence=entry.sequence,
            parent_sequence=execution.parent_sequence,
            tool_call_id=tool_call.id,
            tool=tool_call.name,
            args=self.event_output_sanitizer.sanitize_args(tool_call.args),
        )

    def _emit_tool_result(
        self,
        execution: "_ToolCallExecution",
        entry: AgentContextEntry,
        result: ToolResult,
    ) -> None:
        output = self.event_output_sanitizer.sanitize_output(
            {
                "text": result.text or "",
                "value": result.data,
                "body_ref": None,
            }
        )
        data = output.get("value") if isinstance(output.get("value"), dict) else {}
        text = output.get("text") if isinstance(output.get("text"), str) else None
        self.event_emitter.emit_tool_result(
            run_id=execution.run_id,
            step_id=execution.step_id,
            turn_id=execution.turn_id,
            sequence=entry.sequence,
            parent_sequence=execution.parent_sequence,
            tool_call_id=execution.tool_call.id,
            tool=result.name,
            status=result.status.value,
            data=data,
            text=text,
            error=result.error,
        )

    def _execute_process_tool(
        self,
        execution: "_ToolCallExecution",
        prepared: PreparedTool,
    ) -> ToolResult | None:
        tool = prepared.tool
        if not isinstance(tool, ProcessTool):
            raise ValueError(f"Agent tool '{prepared.name}' is not a ProcessTool")

        process_request = tool.call(prepared.request)
        handle = self.process_runner.popen(process_request)
        wait_result = self.process_runner.wait(
            ToolProcessWait(
                handle=handle,
                timeout=process_request.timeout,
                interrupt=ToolProcessInterrupt(
                    run_id=execution.run_id,
                    signal=self,
                ),
            )
        )
        if wait_result.status == ToolProcessWaitStatus.INTERRUPTED:
            return None
        if wait_result.status == ToolProcessWaitStatus.TIMEOUT:
            return self._timeout_result(prepared=prepared, timeout=process_request.timeout)
        if wait_result.output is None:
            raise ValueError("Tool process completed without output")

        return tool.result(wait_result.output)

    def is_interrupted(self, run_id: str) -> bool:
        interrupted = bool(self.steering.pop(run_id, SteeringAgentInterrupt))
        if interrupted:
            self.steering.pop(run_id, SteeringAgentMessage)
        return interrupted

    def _timeout_result(
        self,
        *,
        prepared: PreparedTool,
        timeout: int | float | None,
    ) -> ToolResult:
        return ToolResult(
            name=prepared.name,
            status=ToolResultStatus.FAILED,
            data={},
            text=None,
            error=(
                "Tool process timed out after "
                f"{self._format_timeout(timeout)}"
            ),
        )

    def _reject_if_tool_call_limit_exceeded(
        self,
        state: "_ToolExecutionState",
    ) -> ToolExecutionResults | None:
        request = state.request
        tool_call_count = len(request.response.tool_calls)
        if tool_call_count <= request.max_tool_calls:
            return None
        self._append_agent_feedback(
            state,
            suffix="tool-limit",
            text=self.feedback.too_many_tool_calls(
                step_id=request.step_id,
                max_tool_calls=request.max_tool_calls,
                tool_call_count=tool_call_count,
            ),
        )
        return ToolExecutionResults(
            items=[
                ToolExecutionResult(
                    tool_call_id=request.turn_id,
                    tool="agent",
                    status=ToolExecutionStatus.INVALID,
                )
            ]
        )

    def _append_tool_call_assistant_message(
        self,
        request: ToolExecutionRequest,
    ) -> int | None:
        content = request.response.content
        if not isinstance(content, str) or not content.strip():
            return None
        assistant_message_entry = self.agent_context_store.append_assistant_message(
            scope=request,
            turn_id=request.turn_id,
            message_type="tool_calls",
            text=content,
        )
        self.event_emitter.emit_assistant_message(
            run_id=request.run_id,
            step_id=request.step_id,
            turn_id=request.turn_id,
            sequence=assistant_message_entry.sequence,
            message_type="tool_calls",
            text=self._sanitize_assistant_text(content),
        )
        return assistant_message_entry.sequence

    def _append_agent_feedback(
        self,
        state: "_ToolExecutionState",
        *,
        suffix: str,
        text: str,
    ) -> None:
        self.agent_context_store.append_user_message(
            scope=state.request,
            turn_id=self._control_turn_id(state, suffix=suffix),
            text=text,
        )

    def _append_interrupt_feedback(self, state: "_ToolExecutionState") -> None:
        self._append_agent_feedback(
            state,
            suffix="interrupt",
            text=self.feedback.user_interrupted_turn(),
        )

    def _prepare_tool_call(
        self,
        state: "_ToolExecutionState",
        tool_call: LLMToolCall,
    ) -> "_PreparedToolCall":
        request = state.request
        tool_call_id = str(tool_call.id).strip() or request.turn_id
        tool_name = str(tool_call.function.name or "").strip() or "unknown"
        try:
            tool_args = self._parse_tool_call_arguments(
                step_id=request.step_id,
                tool_call=tool_call,
            )
        except ValueError as exc:
            return _PreparedToolCall(
                raw=tool_call,
                id=tool_call_id,
                name=tool_name,
                args={},
                error=exc,
            )
        return _PreparedToolCall(
            raw=tool_call,
            id=tool_call_id,
            name=tool_name,
            args=tool_args,
            error=None,
        )

    def _parse_tool_call_arguments(
        self,
        *,
        step_id: str,
        tool_call: LLMToolCall,
    ) -> dict[str, Any]:
        tool_name = str(tool_call.function.name or "").strip()
        if not tool_name:
            raise ValueError(f"Agent step '{step_id}' returned tool_call without tool")

        raw_arguments = str(tool_call.function.arguments_json or "").strip()
        if not raw_arguments:
            return {}

        try:
            parsed_args = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Agent step '{step_id}' returned invalid tool call arguments"
            ) from exc

        if not isinstance(parsed_args, dict):
            raise ValueError(
                f"Agent step '{step_id}' returned tool_call arguments that must be a JSON object"
            )
        return parsed_args

    def _control_turn_id(self, state: "_ToolExecutionState", *, suffix: str) -> str:
        request = state.request
        return f"{request.turn_id}-{suffix}-{request.turn_loop.turn_count + 1}"

    def _sanitize_assistant_text(self, text: str) -> str:
        sanitized = self.event_output_sanitizer.sanitize_output(
            {"text": text, "value": None, "body_ref": None}
        )
        return str(sanitized.get("text", ""))

    def _format_timeout(self, timeout: int | float | None) -> str:
        if isinstance(timeout, int):
            return f"{timeout}s"
        if isinstance(timeout, float):
            return f"{timeout:g}s"
        return "unknown timeout"


@dataclass
class _ToolExecutionState:
    request: ToolExecutionRequest
    parent_sequence: int | None = None
    results: list[ToolExecutionResult] = field(default_factory=list)

    def add(self, result: ToolExecutionResult) -> None:
        self.results.append(result)

    def finish(self) -> ToolExecutionResults:
        return ToolExecutionResults(items=list(self.results))


@dataclass(frozen=True)
class _PreparedToolCall:
    raw: LLMToolCall
    id: str
    name: str
    args: dict[str, Any]
    error: ValueError | None

    @property
    def is_valid(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class _ToolCallExecution:
    state: _ToolExecutionState
    tool_call: _PreparedToolCall

    @property
    def request(self) -> ToolExecutionRequest:
        return self.state.request

    @property
    def parent_sequence(self) -> int | None:
        return self.state.parent_sequence

    @property
    def run_id(self) -> str:
        return self.request.run_id

    @property
    def step_id(self) -> str:
        return self.request.step_id

    @property
    def turn_id(self) -> str:
        return self.request.turn_id
