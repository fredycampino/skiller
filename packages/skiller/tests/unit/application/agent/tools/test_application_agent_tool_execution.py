from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from skiller.application.agent.config.output_truncator import OutputTruncator
from skiller.application.agent.context.agent_context_publisher import (
    AgentContextPublisher,
)
from skiller.application.agent.event.agent_event_publisher import (
    AgentEventPublisher,
)
from skiller.application.agent.event.agent_event_truncator import (
    AgentEventOutputPolicy,
    AgentEventTruncator,
)
from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.application.agent.tools.agent_tool_executor import AgentToolExecutor
from skiller.application.agent.tools.tool_manager import (
    ToolManager,
    ToolPrepareFailure,
    ToolPrepareResult,
)
from skiller.application.tools.notify import NotifyTool
from skiller.application.tools.shell import ShellProcessTool
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntry,
    AgentContextEntryType,
    AgentToolCallPayload,
    AgentToolResultPayload,
)
from skiller.domain.agent.agent_loop_model import AgentLoop
from skiller.domain.agent.agent_run_identity import AgentContext
from skiller.domain.agent.agent_stats_model import (
    AgentContextEntryStats,
    AgentContextStats,
    AgentContextUsageStats,
)
from skiller.domain.agent.llm_model import (
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
    LLMUsage,
)
from skiller.domain.event.event_model import RuntimeEventType
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort
from skiller.domain.run.run_model import RunAgent
from skiller.domain.run.steering_model import (
    SteeringAgentInterrupt,
    SteeringItem,
    SteeringItemType,
)
from skiller.domain.tool.tool_contract import ToolResultStatus
from skiller.domain.tool.tool_execution_model import (
    AgentToolCall,
    AgentToolResult,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionResults,
    ToolExecutionStatus,
)
from skiller.domain.tool.tool_process_model import (
    ToolProcessHandle,
    ToolProcessOutput,
    ToolProcessRequest,
    ToolProcessWait,
    ToolProcessWaitResult,
    ToolProcessWaitStatus,
)

pytestmark = pytest.mark.unit


def test_agent_tool_execution_runs_process_tool() -> None:
    process_runner = _FakeProcessRunner(
        output=ToolProcessOutput(exit_code=0, stdout="ok\n", stderr="")
    )
    context_store = _FakeAgentContextStore()
    runtime_events = _FakeRuntimeEventStore()
    executor = _build_executor(
        context_store=context_store,
        process_runner=process_runner,
        runtime_event_store=runtime_events,
    )

    results = executor.execute(_request_with_tool("shell", '{"command":"pwd"}'))

    assert results == ToolExecutionResults(
        items=[
            ToolExecutionResult(
                tool_call_id="call-1",
                tool="shell",
                status=ToolExecutionStatus.EXECUTED,
            )
        ]
    )
    assert process_runner.requests == [
        ToolProcessRequest(
            command=["/bin/bash", "-lc", "pwd"],
            cwd=str(Path.cwd()),
            env={},
        )
    ]
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.TOOL_CALL,
        AgentContextEntryType.TOOL_RESULT,
    ]
    assert context_store.appended[-1]["payload"]["text"] == "ok"
    assert [event["type"] for event in runtime_events.calls] == [
        "tool_call",
        "tool_result",
    ]


def test_agent_tool_execution_interrupts_process_tool() -> None:
    process_runner = _FakeProcessRunner()
    context_store = _FakeAgentContextStore()
    steering = _FakeSteering()
    steering.pop_results[SteeringAgentInterrupt] = [
        [],
        [SteeringAgentInterrupt()],
    ]
    executor = _build_executor(
        context_store=context_store,
        process_runner=process_runner,
        steering=steering,
    )

    results = executor.execute(_request_with_tool("shell", '{"command":"sleep 10"}'))

    assert results == ToolExecutionResults(
        items=[
            ToolExecutionResult(
                tool_call_id="turn-1",
                tool="agent",
                status=ToolExecutionStatus.INTERRUPTED,
            )
        ]
    )
    assert process_runner.terminated == [ToolProcessHandle(id="proc-1", pid=123)]
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.TOOL_CALL,
        AgentContextEntryType.USER_MESSAGE,
    ]
    assert context_store.appended[-1]["payload"]["text"] == (
        "[Skiller] User interrupted the current tool turn."
    )


def test_agent_tool_execution_falls_back_to_native_tool() -> None:
    context_store = _FakeAgentContextStore()
    executor = _build_executor(context_store=context_store)

    results = executor.execute(_request_with_tool("notify", '{"message":"hello"}'))

    assert results == ToolExecutionResults(
        items=[
            ToolExecutionResult(
                tool_call_id="call-1",
                tool="notify",
                status=ToolExecutionStatus.EXECUTED,
            )
        ]
    )
    assert context_store.appended[-1]["payload"]["text"] == "hello"


def test_agent_tool_execution_runs_multiple_native_tool_calls() -> None:
    context_store = _FakeAgentContextStore()
    runtime_events = _FakeRuntimeEventStore()
    executor = _build_executor(
        context_store=context_store,
        runtime_event_store=runtime_events,
    )
    response = LLMResponse(
        ok=True,
        tool_calls=(
            LLMToolCall(
                id="call-1",
                function=LLMToolCallFunction(
                    name="notify",
                    arguments_json='{"message":"hello"}',
                ),
            ),
            LLMToolCall(
                id="call-2",
                function=LLMToolCallFunction(
                    name="notify",
                    arguments_json='{"message":"world"}',
                ),
            ),
        ),
    )
    request = ToolExecutionRequest(
        context=AgentContext(
            run_id="run-1",
            agent_id="support_agent",
            context_id="ctx-1",
        ),
        turn_id="turn-1",
        response=response,
        allowed_tools=["notify"],
        max_tool_calls=5,
        turn_loop=AgentLoop(max_turns=10),
    )

    results = executor.execute(request)

    assert results == ToolExecutionResults(
        items=[
            ToolExecutionResult(
                tool_call_id="call-1",
                tool="notify",
                status=ToolExecutionStatus.EXECUTED,
            ),
            ToolExecutionResult(
                tool_call_id="call-2",
                tool="notify",
                status=ToolExecutionStatus.EXECUTED,
            ),
        ]
    )
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.TOOL_CALL,
        AgentContextEntryType.TOOL_RESULT,
        AgentContextEntryType.TOOL_CALL,
        AgentContextEntryType.TOOL_RESULT,
    ]
    assert context_store.appended[1]["payload"]["text"] == "hello"
    assert context_store.appended[3]["payload"]["text"] == "world"
    assert [event["type"] for event in runtime_events.calls] == [
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
    ]


def test_agent_tool_execution_persists_prepare_failure_as_tool_result() -> None:
    process_runner = _FakeProcessRunner()
    context_store = _FakeAgentContextStore()
    executor = _build_executor(
        context_store=context_store,
        process_runner=process_runner,
    )

    results = executor.execute(_request_with_tool("shell", '{"command":"cat /etc/passwd"}'))

    assert results == ToolExecutionResults(
        items=[
            ToolExecutionResult(
                tool_call_id="call-1",
                tool="shell",
                status=ToolExecutionStatus.EXECUTED,
            )
        ]
    )
    assert process_runner.requests == []
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.TOOL_CALL,
        AgentContextEntryType.TOOL_RESULT,
    ]
    assert context_store.appended[-1]["payload"]["status"] == ToolResultStatus.FAILED.value
    assert context_store.appended[-1]["payload"]["data"] == {"error": "policy_blocked"}
    assert context_store.appended[-1]["payload"]["error"] == (
        "shell command path escapes workspace"
    )


def test_agent_tool_execution_returns_terminal_prepare_exception_without_tool_result() -> None:
    context_store = _FakeAgentContextStore()
    executor = _build_executor(
        context_store=context_store,
        tool_manager=_RequestExceptionToolManager(),
    )

    results = executor.execute(_request_with_tool("notify", '{"message":"hello"}'))

    assert results == ToolExecutionResults(
        items=[
            ToolExecutionResult(
                tool_call_id="call-1",
                tool="notify",
                status=ToolExecutionStatus.REQUEST_EXCEPTION,
                error_message="request boom",
            )
        ]
    )
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.TOOL_CALL,
    ]


def _build_executor(
    *,
    context_store: "_FakeAgentContextStore",
    process_runner: "_FakeProcessRunner" | None = None,
    steering: "_FakeSteering" | None = None,
    runtime_event_store: "_FakeRuntimeEventStore" | None = None,
    tool_manager=None,
) -> AgentToolExecutor:
    context_publisher = AgentContextPublisher(
        context_store,
        _FakeRunStore(),
        AgentRunnerFeedback(),
    )
    store = runtime_event_store or _FakeRuntimeEventStore()
    return AgentToolExecutor(
        context_publisher=context_publisher,
        event_publisher=AgentEventPublisher(
            store,
            AgentEventTruncator(
                AgentEventOutputPolicy(),
                OutputTruncator(),
            ),
        ),
        steering=steering or _FakeSteering(),
        tool_manager=tool_manager or ToolManager(
            tools=[
                ShellProcessTool(shell="/bin/bash"),
                NotifyTool(),
            ],
        ),
        process_runner=process_runner or _FakeProcessRunner(),
        feedback=AgentRunnerFeedback(),
    )


class _RequestExceptionToolManager:
    def prepare(self, request) -> ToolPrepareResult:
        return ToolPrepareResult(
            ok=False,
            tool_name=request.tool,
            error=ToolPrepareFailure.REQUEST_EXCEPTION,
            error_message="request boom",
        )


def _request_with_tool(tool: str, arguments_json: str) -> ToolExecutionRequest:
    return ToolExecutionRequest(
        context=AgentContext(
            run_id="run-1",
            agent_id="support_agent",
            context_id="ctx-1",
        ),
        turn_id="turn-1",
        response=LLMResponse(
            ok=True,
            tool_calls=(
                LLMToolCall(
                    id="call-1",
                    function=LLMToolCallFunction(
                        name=tool,
                        arguments_json=arguments_json,
                    ),
                ),
            ),
        ),
        allowed_tools=["shell", "notify"],
        max_tool_calls=5,
        turn_loop=AgentLoop(max_turns=10),
    )


class _FakeAgentContextStore:
    def __init__(self) -> None:
        self.entries: list[AgentContextEntry] = []
        self.appended: list[dict[str, object]] = []

    def append_user_message(
        self,
        *,
        context: AgentContext,
        text: str,
    ) -> AgentContextEntry:
        return self._append(
            run_id=context.run_id,
            context_id=context.context_id,
            source_step_id=context.agent_id,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload={"type": "user_message", "text": text},
        )

    def append_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        message_type: str,
        text: str,
        usage: LLMUsage | None = None,
    ) -> AgentContextEntry:
        return self._append(
            run_id=context.run_id,
            context_id=context.context_id,
            source_step_id=context.agent_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={
                "type": "assistant_message",
                "turn_id": turn_id,
                "message_type": message_type,
                "text": text,
                "total_tokens": usage.total_tokens if usage is not None else 0,
            },
            usage=usage,
        )

    def append_tool_call(
        self,
        *,
        context: AgentContext,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry:
        return self._append(
            run_id=context.run_id,
            context_id=context.context_id,
            source_step_id=context.agent_id,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload={
                "type": "tool_call",
                "turn_id": tool_call.turn_id,
                "parent_sequence": tool_call.parent_sequence,
                "tool_call_id": tool_call.tool_call_id,
                "tool": tool_call.tool,
                "args": tool_call.args,
            },
        )

    def append_tool_result(
        self,
        *,
        context: AgentContext,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry:
        result = tool_result.result
        return self._append(
            run_id=context.run_id,
            context_id=context.context_id,
            source_step_id=context.agent_id,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload={
                "type": "tool_result",
                "turn_id": tool_result.turn_id,
                "parent_sequence": tool_result.parent_sequence,
                "tool_call_id": tool_result.tool_call_id,
                "tool": result.name,
                "status": result.status.value,
                "data": result.data,
                "text": result.text,
                "error": result.error,
            },
        )

    def _append(
        self,
        *,
        run_id: str,
        context_id: str,
        source_step_id: str,
        entry_type: AgentContextEntryType,
        payload: dict[str, object],
        usage: LLMUsage | None = None,
    ) -> AgentContextEntry:
        self.appended.append({"entry_type": entry_type, "payload": payload})
        entry = AgentContextEntry(
            id=f"entry-{len(self.entries) + 1}",
            run_id=run_id,
            context_id=context_id,
            sequence=len(self.entries) + 1,
            entry_type=entry_type,
            payload=payload,
            usage=usage,
            source_step_id=source_step_id,
            created_at="2026-05-09T00:00:00Z",
        )
        self.entries.append(entry)
        return entry

    def get_stats(self, *, context_id: str) -> AgentContextStats:
        _ = context_id
        return AgentContextStats(
            entries=AgentContextEntryStats(
                total=0,
                user_messages=0,
                assistant_messages=0,
                tool_calls=0,
                tool_results=0,
            ),
            usage=AgentContextUsageStats(
                entries=0,
                total_prompt_tokens=0,
                total_response_tokens=0,
                total_tokens=0,
            ),
        )


class _FakeRunStore:
    def get_agent(self, *, run_id: str, agent_id: str) -> RunAgent | None:
        _ = run_id, agent_id
        return None

    def attach_agent(self, *, run_id: str, agent_id: str, context_id: str) -> None:
        _ = run_id, agent_id, context_id


class _FakeProcessRunner:
    def __init__(
        self,
        *,
        output: ToolProcessOutput | None = None,
        poll_results: list[int | None] | None = None,
    ) -> None:
        self.output = output or ToolProcessOutput(exit_code=0, stdout="", stderr="")
        self.poll_results = list(poll_results or [0])
        self.requests: list[ToolProcessRequest] = []
        self.terminated: list[ToolProcessHandle] = []

    def popen(self, request: ToolProcessRequest) -> ToolProcessHandle:
        self.requests.append(request)
        return ToolProcessHandle(id="proc-1", pid=123)

    def write(self, handle: ToolProcessHandle, payload: str) -> None:
        return None

    def poll(self, handle: ToolProcessHandle) -> int | None:
        if not self.poll_results:
            return 0
        return self.poll_results.pop(0)

    def read(self, handle: ToolProcessHandle) -> ToolProcessOutput:
        return self.output

    def terminate(self, handle: ToolProcessHandle) -> None:
        self.terminated.append(handle)

    def wait(self, request: ToolProcessWait) -> ToolProcessWaitResult:
        if request.interrupt is not None and request.interrupt.signal.is_interrupted(
            request.interrupt.run_id
        ):
            self.terminate(request.handle)
            return ToolProcessWaitResult(status=ToolProcessWaitStatus.INTERRUPTED)
        return ToolProcessWaitResult(
            status=ToolProcessWaitStatus.COMPLETED,
            output=self.output,
        )


class _FakeSteering:
    def __init__(self) -> None:
        self.items: dict[SteeringItemType, list[SteeringItem]] = {}
        self.pop_results: dict[SteeringItemType, list[list[SteeringItem]]] = {}

    def append(self, run_id: str, item: SteeringItem) -> None:
        _ = run_id
        self.items.setdefault(type(item), []).append(item)

    def pop(self, run_id: str, item_type: SteeringItemType) -> list[SteeringItem]:
        _ = run_id
        if item_type in self.pop_results and self.pop_results[item_type]:
            return self.pop_results[item_type].pop(0)
        return self.items.pop(item_type, [])


@dataclass
class _FakeRuntimeEventStore(RuntimeEventStorePort):
    calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.calls = []

    def emit_max_turns_exhausted(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
    ) -> None:
        self.calls.append(
            {
                "type": "max_turns_exhausted",
                "run_id": run_id,
                "step_id": step_id,
                "turn_id": turn_id,
            }
        )

    def emit_interrupted(
        self,
        *,
        run_id: str,
        step_id: str,
        turn_id: str,
    ) -> None:
        self.calls.append(
            {
                "type": "interrupted",
                "run_id": run_id,
                "step_id": step_id,
                "turn_id": turn_id,
            }
        )

    def emit_assistant_message(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None:
        if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
            raise ValueError("Assistant event requires assistant_message entry")
        if not isinstance(entry.payload, AgentAssistantMessagePayload):
            raise ValueError("Assistant event requires AgentAssistantMessagePayload")
        self.calls.append({"type": "assistant_message", "entry": entry})

    def emit_tool_call(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None:
        if entry.entry_type != AgentContextEntryType.TOOL_CALL:
            raise ValueError("Tool call event requires tool_call entry")
        if not isinstance(entry.payload, AgentToolCallPayload):
            raise ValueError("Tool call event requires AgentToolCallPayload")
        self.calls.append({"type": "tool_call", "entry": entry})

    def emit_tool_result(
        self,
        *,
        entry: AgentContextEntry,
    ) -> None:
        if entry.entry_type != AgentContextEntryType.TOOL_RESULT:
            raise ValueError("Tool result event requires tool_result entry")
        if not isinstance(entry.payload, AgentToolResultPayload):
            raise ValueError("Tool result event requires AgentToolResultPayload")
        self.calls.append({"type": "tool_result", "entry": entry})

    def append_event(self, event):  # noqa: ANN001
        event_type_map = {
            RuntimeEventType.AGENT_ASSISTANT_MESSAGE: "assistant_message",
            RuntimeEventType.AGENT_FINAL_ASSISTANT_MESSAGE: "final_assistant_message",
            RuntimeEventType.AGENT_TOOL_CALL: "tool_call",
            RuntimeEventType.AGENT_TOOL_RESULT: "tool_result",
            RuntimeEventType.AGENT_INTERRUPTED: "interrupted",
            RuntimeEventType.AGENT_MAX_TURNS_EXHAUSTED: "max_turns_exhausted",
        }
        self.calls.append({"type": event_type_map.get(event.type, str(event.type)), "event": event})

    def list_events(self, run_id: str, *, after_sequence=None, limit=None):  # noqa: ANN001
        raise NotImplementedError

    def get_last_event(self, run_id: str):  # noqa: ANN201
        raise NotImplementedError
