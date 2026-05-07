from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from skiller.application.agent.config.event_output_sanitizer import (
    AgentEventOutputSanitizer,
)
from skiller.application.agent.observer.runtime_event_emitter import AgentRuntimeEventEmitter
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.application.agent.tools.tool_turn_executor_model import (
    ToolTurnRequest,
    ToolTurnResult,
    ToolTurnResults,
    ToolTurnStatus,
)
from skiller.application.ports.agent.agent_context_store_port import AgentContextStorePort
from skiller.application.ports.agent.agent_steering_port import AgentSteeringPort
from skiller.application.ports.llm.llm_port import LLMToolCall
from skiller.domain.tool.tool_contract import ToolResult


class AgentToolTurnExecutor:
    def __init__(
        self,
        *,
        agent_context_store: AgentContextStorePort,
        agent_steering: AgentSteeringPort,
        tool_manager: ToolManager | None,
        event_output_sanitizer: AgentEventOutputSanitizer,
        event_emitter: AgentRuntimeEventEmitter,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.agent_steering = agent_steering
        self.tool_manager = tool_manager
        self.event_output_sanitizer = event_output_sanitizer
        self.event_emitter = event_emitter

    def execute(self, request: ToolTurnRequest) -> ToolTurnResults:
        response = request.response
        if not response.tool_calls:
            return ToolTurnResults(items=[])
        limit_result = self._reject_if_tool_call_limit_exceeded(request=request)
        if limit_result is not None:
            return limit_result

        parent_sequence = self._append_tool_turn_assistant_message(request=request)

        results: list[ToolTurnResult] = []
        for tool_call in response.tool_calls:
            interrupt_result = self._interrupt_if_requested(
                request=request,
                results=results,
            )
            if interrupt_result is not None:
                return interrupt_result

            prepared_tool_call = self._prepare_tool_call(
                request=request,
                tool_call=tool_call,
            )
            if prepared_tool_call.error is not None:
                results.append(
                    self._record_invalid_tool_call(
                        request=request,
                        prepared_tool_call=prepared_tool_call,
                    )
                )
                continue

            results.append(
                self._execute_single_tool_call(
                    request=request,
                    parent_sequence=parent_sequence,
                    prepared_tool_call=prepared_tool_call,
                )
            )

        request.turn_loop.advance()
        return ToolTurnResults(items=results)

    def _execute_single_tool_call(
        self,
        *,
        request: ToolTurnRequest,
        parent_sequence: int | None,
        prepared_tool_call: "_PreparedToolCall",
    ) -> ToolTurnResult:
        tool_call_entry = self.agent_context_store.append_tool_call(
            run_id=request.run_id,
            context_id=request.context_id,
            source_step_id=request.step_id,
            turn_id=request.turn_id,
            parent_sequence=parent_sequence,
            tool_call_id=prepared_tool_call.tool_call_id,
            tool=prepared_tool_call.tool_name,
            args=prepared_tool_call.tool_args,
        )
        self.event_emitter.emit_tool_call(
            run_id=request.run_id,
            step_id=request.step_id,
            turn_id=request.turn_id,
            sequence=tool_call_entry.sequence,
            parent_sequence=parent_sequence,
            tool_call_id=prepared_tool_call.tool_call_id,
            tool=prepared_tool_call.tool_name,
            args=self.event_output_sanitizer.sanitize_args(prepared_tool_call.tool_args),
        )
        tool_result = self._execute_tool(
            run_id=request.run_id,
            step_id=request.step_id,
            context_id=request.context_id,
            turn_id=request.turn_id,
            tool_call_id=prepared_tool_call.tool_call_id,
            tool=prepared_tool_call.tool_name,
            args=prepared_tool_call.tool_args,
            allowed_tools=request.allowed_tools,
        )
        tool_result_entry = self.agent_context_store.append_tool_result(
            run_id=request.run_id,
            context_id=request.context_id,
            source_step_id=request.step_id,
            turn_id=request.turn_id,
            parent_sequence=parent_sequence,
            tool_call_id=prepared_tool_call.tool_call_id,
            tool=tool_result.name,
            status=tool_result.status.value,
            data=tool_result.data,
            text=tool_result.text,
            error=tool_result.error,
        )
        self.event_emitter.emit_tool_result(
            run_id=request.run_id,
            step_id=request.step_id,
            turn_id=request.turn_id,
            sequence=tool_result_entry.sequence,
            parent_sequence=parent_sequence,
            tool_call_id=prepared_tool_call.tool_call_id,
            tool=tool_result.name,
            context_ref=f"agent_context:{tool_result_entry.id}",
            output=self.event_output_sanitizer.sanitize_output(
                {
                    "text": tool_result.text or "",
                    "value": tool_result.data,
                    "body_ref": None,
                }
            ),
        )
        return ToolTurnResult(
            tool_call_id=prepared_tool_call.tool_call_id,
            tool=tool_result.name,
            status=ToolTurnStatus.EXECUTED,
        )

    def _reject_if_tool_call_limit_exceeded(
        self,
        *,
        request: ToolTurnRequest,
    ) -> ToolTurnResults | None:
        tool_call_count = len(request.response.tool_calls)
        if tool_call_count <= request.max_tool_calls:
            return None
        self.agent_context_store.append_user_message(
            run_id=request.run_id,
            context_id=request.context_id,
            source_step_id=request.step_id,
            turn_id=self._control_turn_id(request=request, suffix="tool-limit"),
            text=self._build_tool_call_limit_feedback(
                step_id=request.step_id,
                max_tool_calls=request.max_tool_calls,
                tool_call_count=tool_call_count,
            ),
        )
        request.turn_loop.advance()
        return ToolTurnResults(
            items=[
                ToolTurnResult(
                    tool_call_id=request.turn_id,
                    tool="agent",
                    status=ToolTurnStatus.INVALID,
                )
            ]
        )

    def _append_tool_turn_assistant_message(
        self,
        *,
        request: ToolTurnRequest,
    ) -> int | None:
        content = request.response.content
        if not isinstance(content, str) or not content.strip():
            return None
        assistant_message_entry = self.agent_context_store.append_assistant_message(
            run_id=request.run_id,
            context_id=request.context_id,
            source_step_id=request.step_id,
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

    def _interrupt_if_requested(
        self,
        *,
        request: ToolTurnRequest,
        results: list[ToolTurnResult],
    ) -> ToolTurnResults | None:
        if not self.agent_steering.consume_abort_turn(request.run_id):
            return None
        self.agent_context_store.append_user_message(
            run_id=request.run_id,
            context_id=request.context_id,
            source_step_id=request.step_id,
            turn_id=self._control_turn_id(request=request, suffix="interrupt"),
            text="User interrupted the current agent turn.",
        )
        results.append(
            ToolTurnResult(
                tool_call_id=request.turn_id,
                tool="agent",
                status=ToolTurnStatus.INTERRUPTED,
            )
        )
        request.turn_loop.advance()
        return ToolTurnResults(items=results)

    def _prepare_tool_call(
        self,
        *,
        request: ToolTurnRequest,
        tool_call: LLMToolCall,
    ) -> "_PreparedToolCall":
        tool_call_id = str(tool_call.id).strip() or request.turn_id
        tool_name = str(tool_call.function.name or "").strip() or "unknown"
        try:
            tool_args = self._parse_tool_call_arguments(
                step_id=request.step_id,
                tool_call=tool_call,
            )
        except ValueError as exc:
            return _PreparedToolCall(
                tool_call=tool_call,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                tool_args=None,
                error=exc,
            )
        return _PreparedToolCall(
            tool_call=tool_call,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_args=tool_args,
            error=None,
        )

    def _record_invalid_tool_call(
        self,
        *,
        request: ToolTurnRequest,
        prepared_tool_call: "_PreparedToolCall",
    ) -> ToolTurnResult:
        if prepared_tool_call.error is None:
            raise ValueError("Invalid tool call requires error")
        self.agent_context_store.append_user_message(
            run_id=request.run_id,
            context_id=request.context_id,
            source_step_id=request.step_id,
            turn_id=self._control_turn_id(request=request, suffix="tool-format"),
            text=self._build_invalid_tool_call_feedback(
                step_id=request.step_id,
                tool_call=prepared_tool_call.tool_call,
                error=prepared_tool_call.error,
            ),
        )
        return ToolTurnResult(
            tool_call_id=prepared_tool_call.tool_call_id,
            tool=prepared_tool_call.tool_name,
            status=ToolTurnStatus.INVALID,
        )

    def _execute_tool(
        self,
        *,
        run_id: str,
        step_id: str,
        context_id: str,
        turn_id: str,
        tool_call_id: str,
        tool: str,
        args: dict[str, Any],
        allowed_tools: list[str],
    ) -> ToolResult:
        if self.tool_manager is None:
            raise ValueError(f"Step '{step_id}' requires tool_manager for tools")
        return self.tool_manager.execute(
            AgentToolRequest(
                run_id=run_id,
                step_id=step_id,
                context_id=context_id,
                turn_id=turn_id,
                tool_call_id=tool_call_id,
                tool=tool,
                args=args,
                allowed_tools=allowed_tools,
            )
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

    def _build_invalid_tool_call_feedback(
        self,
        *,
        step_id: str,
        tool_call: LLMToolCall,
        error: ValueError,
    ) -> str:
        tool_name = str(tool_call.function.name or "").strip() or "unknown"
        detail = str(error).strip() or "invalid tool call arguments"
        return (
            f"Invalid tool call arguments in step '{step_id}' for tool '{tool_name}': "
            f"{detail}. Return a single JSON object with valid arguments."
        )

    def _build_tool_call_limit_feedback(
        self,
        *,
        step_id: str,
        max_tool_calls: int,
        tool_call_count: int,
    ) -> str:
        return (
            f"Too many tool calls in step '{step_id}': received {tool_call_count}, "
            f"maximum allowed is {max_tool_calls}. Return at most {max_tool_calls} tool "
            "call(s) in one response."
        )

    def _control_turn_id(self, *, request: ToolTurnRequest, suffix: str) -> str:
        return f"{request.turn_id}-{suffix}-{request.turn_loop.turn_count + 1}"

    def _sanitize_assistant_text(self, text: str) -> str:
        sanitized = self.event_output_sanitizer.sanitize_output(
            {"text": text, "value": None, "body_ref": None}
        )
        return str(sanitized.get("text", ""))


@dataclass(frozen=True)
class _PreparedToolCall:
    tool_call: LLMToolCall
    tool_call_id: str
    tool_name: str
    tool_args: dict[str, Any] | None
    error: ValueError | None
