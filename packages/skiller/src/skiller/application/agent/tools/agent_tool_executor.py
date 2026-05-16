from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from skiller.application.agent.context.agent_context_publisher import (
    AgentContextPublisher,
)
from skiller.application.agent.event.agent_event_publisher import (
    AgentEventPublisher,
)
from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.application.agent.tools.tool_manager import (
    PreparedTool,
    ToolManager,
    ToolPrepareFailure,
)
from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.domain.agent.llm_model import LLMToolCall
from skiller.domain.run.steering_model import SteeringAgentInterrupt, SteeringAgentMessage
from skiller.domain.shared.steering_port import SteeringPort
from skiller.domain.tool.tool_contract import ProcessTool, ToolResult, ToolResultStatus
from skiller.domain.tool.tool_execution_model import (
    AgentToolCall,
    AgentToolResult,
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


class AgentToolExecutor(ToolProcessInterruptSignal):
    def __init__(
        self,
        *,
        context_publisher: AgentContextPublisher,
        event_publisher: AgentEventPublisher,
        steering: SteeringPort,
        tool_manager: ToolManager,
        process_runner: ToolProcessPort,
        feedback: AgentRunnerFeedback,
    ) -> None:
        self.context_publisher = context_publisher
        self.event_publisher = event_publisher
        self.steering = steering
        self.tool_manager = tool_manager
        self.process_runner = process_runner
        self.feedback = feedback

    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResults:
        # No tool calls means the tool loop has nothing to execute.
        if not request.response.tool_calls:
            return ToolExecutionResults(items=[])

        state = _ToolExecutionState(request=request)
        tool_call_count = len(request.response.tool_calls)
        if tool_call_count > request.max_tool_calls:
            self.context_publisher.publish_tool_limit_feedback(
                request=request,
                tool_call_count=tool_call_count,
            )
            return ToolExecutionResults(
                items=[
                    ToolExecutionResult(
                        tool_call_id=state.request.turn_id,
                        tool="agent",
                        status=ToolExecutionStatus.INVALID,
                    )
                ]
            )

        if request.response.has_text_content:
            assistant_message_entry = self.context_publisher.publish_assistant_message(
                scope=request,
                turn_id=request.turn_id,
                message_type="tool_calls",
                text=request.response.content,
                usage=request.response.usage,
            )
            self.event_publisher.emit_assistant_message(entry=assistant_message_entry)
            state.parent_sequence = assistant_message_entry.sequence

        for raw_tool_call in request.response.tool_calls:
            # User interrupt stops the current tool loop immediately.
            if self.is_interrupted(request.run_id):
                self.context_publisher.publish_interrupt_feedback(request=request)
                state.add(
                    ToolExecutionResult(
                        tool_call_id=request.turn_id,
                        tool="agent",
                        status=ToolExecutionStatus.INTERRUPTED,
                    )
                )
                return state.finish()

            try:
                parsed_args = self._parse_tool_arguments(raw_tool_call)
            except ValueError as error:
                self.context_publisher.publish_invalid_tool_call(
                    request=request,
                    tool_call=raw_tool_call,
                    error=error,
                )
                result = ToolExecutionResult(
                    tool_call_id=raw_tool_call.id,
                    tool=_tool_name(raw_tool_call),
                    status=ToolExecutionStatus.INVALID,
                )
                state.add(result)
                continue

            agent_tool_call = AgentToolCall(
                turn_id=request.turn_id,
                tool_call_id=raw_tool_call.id,
                tool=_tool_name(raw_tool_call),
                parent_sequence=state.parent_sequence,
                args=parsed_args,
            )
            tool_call_entry = self.context_publisher.publish_tool_call(
                request=request,
                tool_call=agent_tool_call,
            )
            self.event_publisher.emit_tool_call(entry=tool_call_entry)

            prepare_result = self.tool_manager.prepare(
                AgentToolRequest(
                    run_id=request.run_id,
                    step_id=request.step_id,
                    context_id=request.context_id,
                    turn_id=request.turn_id,
                    tool_call_id=agent_tool_call.tool_call_id,
                    tool=agent_tool_call.tool,
                    args=agent_tool_call.args,
                    allowed_tools=request.allowed_tools,
                )
            )
            # Process tools run through the managed process runner.
            if prepare_result.ok and isinstance(prepare_result.prepared.tool, ProcessTool):
                tool_result = self._execute_process_tool(
                    run_id=request.run_id,
                    prepared=prepare_result.prepared,
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
                        tool_call_id=raw_tool_call.id,
                        tool=_tool_name(raw_tool_call),
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
                self.context_publisher.publish_interrupt_feedback(request=request)
                state.add(
                    ToolExecutionResult(
                        tool_call_id=request.turn_id,
                        tool="agent",
                        status=ToolExecutionStatus.INTERRUPTED,
                    )
                )
                return state.finish()

            agent_tool_result = AgentToolResult(
                turn_id=request.turn_id,
                tool_call_id=agent_tool_call.tool_call_id,
                parent_sequence=agent_tool_call.parent_sequence,
                result=tool_result,
            )
            tool_result_entry = self.context_publisher.publish_tool_result(
                request=request,
                tool_result=agent_tool_result,
            )
            self.event_publisher.emit_tool_result(entry=tool_result_entry)
            state.add(
                ToolExecutionResult(
                    tool_call_id=raw_tool_call.id,
                    tool=tool_result.name,
                    status=ToolExecutionStatus.EXECUTED,
                )
            )

        return state.finish()

    def _execute_process_tool(
        self,
        run_id: str,
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
                    run_id=run_id,
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
            self.steering.append(run_id, SteeringAgentMessage(text="Agent interrupted by user"))
        return interrupted

    def _timeout_result(
        self,
        *,
        prepared: PreparedTool,
        timeout: int,
    ) -> ToolResult:
        return ToolResult(
            name=prepared.name,
            status=ToolResultStatus.FAILED,
            data={"error": "timeout", "timeout": timeout},
            text=None,
            error=f"Tool '{prepared.name}' timed out after {timeout}s",
        )

    def _parse_tool_arguments(
        self,
        tool_call: LLMToolCall,
    ) -> dict[str, Any]:
        arguments_json = tool_call.function.arguments_json or "{}"
        try:
            parsed = json.loads(arguments_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc.msg}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("arguments must decode to a JSON object")

        return parsed

@dataclass
class _ToolExecutionState:
    request: ToolExecutionRequest
    items: list[ToolExecutionResult] = field(default_factory=list)
    parent_sequence: int | None = None

    def add(self, item: ToolExecutionResult) -> None:
        self.items.append(item)

    def finish(self) -> ToolExecutionResults:
        return ToolExecutionResults(items=list(self.items))


def _tool_name(tool_call: LLMToolCall) -> str:
    return str(tool_call.function.name or "").strip() or "unknown"
