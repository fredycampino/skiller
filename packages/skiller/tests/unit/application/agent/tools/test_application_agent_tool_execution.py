from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from skiller.application.agent.config.event_output_sanitizer import (
    AgentEventOutputPolicy,
    AgentEventOutputSanitizer,
)
from skiller.application.agent.feedback import AgentRunnerFeedback
from skiller.application.agent.tools.agent_tool_execution import AgentToolExecution
from skiller.application.agent.tools.tool_manager import (
    ToolManager,
    ToolPrepareFailure,
    ToolPrepareResult,
)
from skiller.application.tools.notify import NotifyTool
from skiller.application.tools.shell import ShellProcessTool
from skiller.domain.agent.agent_context_model import (
    AgentContextEntry,
    AgentContextEntryType,
)
from skiller.domain.agent.agent_loop_model import AgentLoop
from skiller.domain.agent.llm_model import (
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
)
from skiller.domain.run.steering_model import (
    SteeringAgentInterrupt,
    SteeringItem,
    SteeringItemType,
)
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus
from skiller.domain.tool.tool_execution_model import (
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
    events = _FakeEventEmitter()
    executor = _build_executor(
        context_store=context_store,
        event_emitter=events,
        process_runner=process_runner,
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
    assert [event["type"] for event in events.calls] == ["tool_call", "tool_result"]


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
    event_emitter: "_FakeEventEmitter" | None = None,
    tool_manager=None,
) -> AgentToolExecution:
    return AgentToolExecution(
        agent_context_store=context_store,
        steering=steering or _FakeSteering(),
        tool_manager=tool_manager or ToolManager(
            tools=[
                ShellProcessTool(shell="/bin/bash"),
                NotifyTool(),
            ],
        ),
        process_runner=process_runner or _FakeProcessRunner(),
        feedback=AgentRunnerFeedback(),
        event_output_sanitizer=AgentEventOutputSanitizer(AgentEventOutputPolicy()),
        event_emitter=event_emitter or _FakeEventEmitter(),
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
        run_id="run-1",
        step_id="support_agent",
        context_id="ctx-1",
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
        scope,
        turn_id: str,
        text: str,
    ) -> AgentContextEntry:
        return self._append(
            scope=scope,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload={"type": "user_message", "text": text},
        )

    def append_assistant_message(
        self,
        *,
        scope,
        turn_id: str,
        message_type: str,
        text: str,
    ) -> AgentContextEntry:
        return self._append(
            scope=scope,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={
                "type": "assistant_message",
                "turn_id": turn_id,
                "message_type": message_type,
                "text": text,
            },
        )

    def append_tool_call(
        self,
        *,
        scope,
        turn_id: str,
        parent_sequence: int | None,
        tool_call_id: str,
        tool: str,
        args: dict[str, object],
    ) -> AgentContextEntry:
        return self._append(
            scope=scope,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload={
                "type": "tool_call",
                "turn_id": turn_id,
                "parent_sequence": parent_sequence,
                "tool_call_id": tool_call_id,
                "tool": tool,
                "args": args,
            },
        )

    def append_tool_result(
        self,
        *,
        scope,
        turn_id: str,
        parent_sequence: int | None,
        tool_call_id: str,
        result: ToolResult,
    ) -> AgentContextEntry:
        return self._append(
            scope=scope,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload={
                "type": "tool_result",
                "turn_id": turn_id,
                "parent_sequence": parent_sequence,
                "tool_call_id": tool_call_id,
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
        scope,
        entry_type: AgentContextEntryType,
        payload: dict[str, object],
    ) -> AgentContextEntry:
        self.appended.append({"entry_type": entry_type, "payload": payload})
        entry = AgentContextEntry(
            id=f"entry-{len(self.entries) + 1}",
            run_id=scope.run_id,
            context_id=scope.context_id,
            sequence=len(self.entries) + 1,
            entry_type=entry_type,
            payload=payload,
            source_step_id=scope.agent_id,
            idempotency_key=f"entry-{len(self.entries) + 1}",
            created_at="2026-05-09T00:00:00Z",
        )
        self.entries.append(entry)
        return entry


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
class _FakeEventEmitter:
    calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.calls = []

    def emit_assistant_message(self, **kwargs) -> None:  # noqa: ANN003
        self.calls.append({"type": "assistant_message", **kwargs})

    def emit_tool_call(self, **kwargs) -> None:  # noqa: ANN003
        self.calls.append({"type": "tool_call", **kwargs})

    def emit_tool_result(self, **kwargs) -> None:  # noqa: ANN003
        self.calls.append({"type": "tool_result", **kwargs})
