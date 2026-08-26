from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from skiller.application.agent.config.output_truncator import OutputTruncator
from skiller.application.agent.context.agent_context_marker_calculator import (
    AgentContextMarkerCalculator,
)
from skiller.application.agent.context.agent_context_publisher import (
    AgentContextPublisher,
)
from skiller.application.agent.event.agent_event_draft_builder import (
    AgentEventDraftBuilder,
)
from skiller.application.agent.event.agent_event_publisher import (
    AgentEventPublisher,
)
from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.application.agent.tools.agent_tool_executor import AgentToolExecutor
from skiller.application.agent.tools.tool_manager import (
    PreparedTool,
    ToolManager,
    ToolPrepareFailure,
    ToolPrepareResult,
)
from skiller.application.tools.notify import NotifyTool
from skiller.application.tools.shell import ShellProcessTool
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.domain.agent.config.model import (
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
)
from skiller.domain.agent.context.model import (
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextMetrics,
    AgentContextPayload,
    AgentContextState,
    AgentContextUsageMarker,
)
from skiller.domain.agent.context.stats_model import (
    AgentContextObservedStats,
    AgentContextObservedWindowStats,
)
from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import (
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
    LLMUsage,
)
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.run.identity import AgentContext
from skiller.domain.agent.run.loop import AgentLoop
from skiller.domain.event.event_model import RuntimeEventType
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort
from skiller.domain.run.run_model import RunAgent
from skiller.domain.run.steering_model import (
    SteeringAgentInterrupt,
    SteeringItem,
    SteeringItemType,
)
from skiller.domain.tool.tool_contract import (
    ToolResult,
    ToolResultStatus,
    ToolRuntimeConfigs,
)
from skiller.domain.tool.tool_execution_model import (
    AgentToolCall,
    AgentToolResult,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionResults,
    ToolExecutionStatus,
)
from skiller.domain.tool.tool_process_model import (
    ToolProcessCompleted,
    ToolProcessHandle,
    ToolProcessInterrupted,
    ToolProcessOutput,
    ToolProcessRequest,
    ToolProcessStarted,
    ToolProcessStartFailed,
    ToolProcessStartResult,
    ToolProcessWait,
    ToolProcessWaitFailed,
    ToolProcessWaitResult,
)

pytestmark = pytest.mark.unit


def _model(value: str, context_window_tokens: int) -> LLMModelDefinition:
    return LLMModelDefinition(
        model=value, context_window_tokens=context_window_tokens, max_output_tokens=None
    )


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
    assert context_store.appended[-1]["payload"]["data"]["stdout"] == "ok\n"
    assert "text" not in context_store.appended[-1]["payload"]
    assert [event["type"] for event in runtime_events.calls] == [
        "tool_call",
        "tool_result",
    ]


def test_agent_tool_execution_keeps_tool_result_text_out_of_context_payload() -> None:
    context_store = _FakeAgentContextStore()
    runtime_events = _FakeRuntimeEventStore()
    executor = _build_executor(
        context_store=context_store,
        runtime_event_store=runtime_events,
        tool_manager=_TextOnlyToolManager(),
    )

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
    assert context_store.appended[-1]["payload"]["status"] == ToolResultStatus.COMPLETED.value
    assert context_store.appended[-1]["payload"]["data"] == {"ok": True}
    assert "text" not in context_store.appended[-1]["payload"]
    assert runtime_events.calls[-1]["event"].payload.body.text == f"{'x' * 600}..."


def test_agent_tool_execution_rejects_large_tool_result_data_before_publish() -> None:
    context_store = _FakeAgentContextStore()
    runtime_events = _FakeRuntimeEventStore()
    executor = _build_executor(
        context_store=context_store,
        runtime_event_store=runtime_events,
        tool_manager=_LargeDataToolManager(),
    )

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
    payload = context_store.appended[-1]["payload"]
    assert payload["status"] == ToolResultStatus.FAILED.value
    assert payload["data"] == {}
    assert "Tool result data from 'notify' is too large" in str(payload["error"])
    assert "maximum allowed is 40000 bytes" in str(payload["error"])
    assert "text" not in payload

    body = runtime_events.calls[-1]["event"].payload.body
    assert body.status == ToolResultStatus.FAILED.value
    assert body.data == {}
    assert body.text is None
    assert "Tool result data from 'notify' is too large" in str(body.error)
    assert "maximum allowed is 40000 bytes" in str(body.error)


def test_agent_tool_execution_rejects_large_tool_result_error_before_publish() -> None:
    context_store = _FakeAgentContextStore()
    runtime_events = _FakeRuntimeEventStore()
    executor = _build_executor(
        context_store=context_store,
        runtime_event_store=runtime_events,
        tool_manager=_LargeErrorToolManager(),
    )

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
    payload = context_store.appended[-1]["payload"]
    assert payload["status"] == ToolResultStatus.FAILED.value
    assert payload["data"] == {}
    assert "Tool result error from 'notify' is too large" in str(payload["error"])
    assert "maximum allowed is 40000 bytes" in str(payload["error"])
    assert "text" not in payload

    body = runtime_events.calls[-1]["event"].payload.body
    assert body.status == ToolResultStatus.FAILED.value
    assert body.data == {}
    assert body.text is None
    assert "Tool result error from 'notify' is too large" in str(body.error)
    assert "maximum allowed is 40000 bytes" in str(body.error)


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
                tool_call_id="call-1",
                tool="shell",
                status=ToolExecutionStatus.INTERRUPTED,
            )
        ]
    )
    assert process_runner.terminated == [ToolProcessHandle(id="proc-1", pid=123)]
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.TOOL_CALL,
        AgentContextEntryType.TOOL_RESULT,
    ]
    assert context_store.appended[1]["payload"] == {
        "type": "tool_result",
        "turn_id": "turn-1",
        "parent_sequence": None,
        "tool_call_id": "call-1",
        "tool": "shell",
        "status": "INTERRUPTED",
        "data": {"error": "interrupted"},
        "error": "Tool execution interrupted by user",
    }


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
    assert context_store.appended[-1]["payload"]["data"] == {"message": "hello"}
    assert "text" not in context_store.appended[-1]["payload"]


def test_agent_tool_execution_runs_multiple_native_tool_calls() -> None:
    context_store = _FakeAgentContextStore()
    runtime_events = _FakeRuntimeEventStore()
    executor = _build_executor(
        context_store=context_store,
        runtime_event_store=runtime_events,
    )
    response = LLMResponse(
        model=_model("model1", 100_000),
        finish_type=LLMFinishType.TOOL_CALLS,
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
        runtime_configs=ToolRuntimeConfigs(),
        event_config=_event_output_config(),
        max_tool_calls=5,
        max_tool_result_bytes=40_000,
        context_metrics=AgentContextMetrics(
            effective_window_tokens=100_000,
            max_total_tokens_ratio=0.8,
            window_width_tokens=100_000,
            model_context_window_tokens=100_000,
        ),
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
    assert context_store.appended[1]["payload"]["data"] == {"message": "hello"}
    assert context_store.appended[3]["payload"]["data"] == {"message": "world"}
    assert "text" not in context_store.appended[1]["payload"]
    assert "text" not in context_store.appended[3]["payload"]
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
        "shell command path escapes allowed_paths: /etc/passwd"
    )


def test_agent_tool_execution_persists_invalid_shell_cwd_as_tool_result() -> None:
    process_runner = _FakeProcessRunner()
    context_store = _FakeAgentContextStore()
    executor = _build_executor(
        context_store=context_store,
        process_runner=process_runner,
    )

    results = executor.execute(
        _request_with_tool(
            "shell",
            '{"command":"pwd","cwd":"/outside/workspace"}',
        )
    )

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
        "shell cwd escapes allowed_paths: /outside/workspace"
    )


@pytest.mark.parametrize(
    ("start_error", "wait_error", "error_code", "error_message"),
    [
        ("process could not start", None, "process_start_failed", "process could not start"),
        (None, "process could not complete", "process_wait_failed", "process could not complete"),
    ],
)
def test_agent_tool_execution_persists_process_failures_as_tool_results(
    start_error: str | None,
    wait_error: str | None,
    error_code: str,
    error_message: str,
) -> None:
    process_runner = _FakeProcessRunner(
        start_error=start_error,
        wait_error=wait_error,
    )
    context_store = _FakeAgentContextStore()
    executor = _build_executor(
        context_store=context_store,
        process_runner=process_runner,
    )

    results = executor.execute(_request_with_tool("shell", '{"command":"pwd"}'))

    assert results.items[0].status == ToolExecutionStatus.EXECUTED
    assert context_store.appended[-1]["payload"]["status"] == ToolResultStatus.FAILED.value
    assert context_store.appended[-1]["payload"]["data"] == {"error": error_code}
    assert context_store.appended[-1]["payload"]["error"] == error_message


def test_agent_tool_execution_persists_nonexistent_shell_cwd_as_tool_result(
    tmp_path: Path,
) -> None:
    process_runner = _FakeProcessRunner()
    context_store = _FakeAgentContextStore()
    executor = _build_executor(
        context_store=context_store,
        process_runner=process_runner,
    )
    allowed = tmp_path / "workspace"
    allowed.mkdir()
    missing = allowed / "missing"
    runtime_configs = ToolRuntimeConfigs(
        items=(
            ShellToolRuntimeConfig(
                definition=ShellProcessTool,
                allowed_paths=(allowed,),
            ),
        ),
    )
    request = replace(
        _request_with_tool(
            "shell",
            f'{{"command":"pwd","cwd":"{missing}"}}',
        ),
        runtime_configs=runtime_configs,
    )

    results = executor.execute(request)

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
        f"shell cwd does not exist: {missing}"
    )


def test_agent_tool_execution_returns_terminal_prepare_exception_without_tool_result() -> None:
    context_store = _FakeAgentContextStore()
    runtime_events = _FakeRuntimeEventStore()
    executor = _build_executor(
        context_store=context_store,
        runtime_event_store=runtime_events,
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
    assert [event["type"] for event in runtime_events.calls] == ["tool_call"]


def _build_executor(
    *,
    context_store: "_FakeAgentContextStore",
    process_runner: "_FakeProcessRunner" | None = None,
    steering: "_FakeSteering" | None = None,
    runtime_event_store: "_FakeRuntimeEventStore" | None = None,
    tool_manager=None,
) -> AgentToolExecutor:
    run_agent_store = _FakeRunAgentStore()
    agent_context_state = _FakeAgentContextState()
    marker_calculator = AgentContextMarkerCalculator(
        agent_context_store=context_store,
        agent_context_state=agent_context_state,
    )
    context_publisher = AgentContextPublisher(
        context_store,
        run_agent_store,
        marker_calculator,
        AgentRunnerFeedback(),
    )
    store = runtime_event_store or _FakeRuntimeEventStore()
    return AgentToolExecutor(
        context_publisher=context_publisher,
        event_publisher=AgentEventPublisher(
            store,
            AgentEventDraftBuilder(),
            OutputTruncator(),
        ),
        steering=steering or _FakeSteering(),
        tool_manager=tool_manager
        or ToolManager(
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


class _TextOnlyToolManager:
    def prepare(self, request) -> ToolPrepareResult:
        return ToolPrepareResult(
            ok=True,
            tool_name=request.tool,
            prepared=PreparedTool(
                name=request.tool,
                tool=NotifyTool(),
                request=request,
                config=request.runtime_config,
            ),
        )

    def execute_prepared(self, prepared: PreparedTool) -> ToolResult:
        _ = prepared
        return ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"ok": True},
            text="x" * 60_000,
            error=None,
        )


class _LargeDataToolManager:
    def prepare(self, request) -> ToolPrepareResult:
        return ToolPrepareResult(
            ok=True,
            tool_name=request.tool,
            prepared=PreparedTool(
                name=request.tool,
                tool=NotifyTool(),
                request=request,
                config=request.runtime_config,
            ),
        )

    def execute_prepared(self, prepared: PreparedTool) -> ToolResult:
        _ = prepared
        return ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"content": "x" * 60_000},
            text="short summary",
            error=None,
        )


class _LargeErrorToolManager:
    def prepare(self, request) -> ToolPrepareResult:
        return ToolPrepareResult(
            ok=True,
            tool_name=request.tool,
            prepared=PreparedTool(
                name=request.tool,
                tool=NotifyTool(),
                request=request,
                config=request.runtime_config,
            ),
        )

    def execute_prepared(self, prepared: PreparedTool) -> ToolResult:
        _ = prepared
        return ToolResult(
            name="notify",
            status=ToolResultStatus.FAILED,
            data={"ok": False},
            text=None,
            error="x" * 60_000,
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
            model=_model("model1", 100_000),
            finish_type=LLMFinishType.TOOL_CALLS,
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
        runtime_configs=ToolRuntimeConfigs(
            items=(
                ShellToolRuntimeConfig(
                    definition=ShellProcessTool,
                ),
            ),
        ),
        event_config=_event_output_config(),
        max_tool_calls=5,
        max_tool_result_bytes=40_000,
        context_metrics=AgentContextMetrics(
            effective_window_tokens=100_000,
            max_total_tokens_ratio=0.8,
            window_width_tokens=100_000,
            model_context_window_tokens=100_000,
        ),
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

    def append_tool_calls_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None = None,
        delta_tokens: int | None = 0,
        compaction_id: int | None = 0,
    ) -> AgentContextEntry:
        return self._append(
            run_id=context.run_id,
            context_id=context.context_id,
            source_step_id=context.agent_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={
                "type": "assistant_message",
                "turn_id": turn_id,
                "message_type": AgentAssistantMessageType.TOOL_CALLS.value,
                "text": text,
            },
            usage=usage,
            message_type=AgentAssistantMessageType.TOOL_CALLS,
            delta_tokens=delta_tokens,
            compaction_id=compaction_id,
        )

    def append_final_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None,
        delta_tokens: int | None,
        compaction_id: int | None,
    ) -> AgentContextEntry:
        return self._append(
            run_id=context.run_id,
            context_id=context.context_id,
            source_step_id=context.agent_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={
                "type": "assistant_message",
                "turn_id": turn_id,
                "message_type": AgentAssistantMessageType.FINAL.value,
                "text": text,
            },
            usage=usage,
            message_type=AgentAssistantMessageType.FINAL,
            delta_tokens=delta_tokens,
            compaction_id=compaction_id,
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
        message_type: AgentAssistantMessageType | None = None,
        delta_tokens: int | None = None,
        compaction_id: int | None = None,
    ) -> AgentContextEntry:
        self.appended.append(
            {
                "entry_type": entry_type,
                "payload": payload,
                "message_type": message_type.value if message_type else None,
                "delta_tokens": delta_tokens,
                "compaction_id": compaction_id,
            }
        )
        entry = AgentContextEntry(
            id=f"entry-{len(self.entries) + 1}",
            run_id=run_id,
            context_id=context_id,
            sequence=len(self.entries) + 1,
            entry_type=entry_type,
            payload=payload,
            usage=usage,
            message_type=message_type,
            delta_tokens=delta_tokens,
            compaction_id=compaction_id,
            source_step_id=source_step_id,
            created_at="2026-05-09T00:00:00Z",
        )
        self.entries.append(entry)
        return entry

    def get_stats(self, *, context_id: str) -> AgentContextObservedStats:
        _ = context_id
        return AgentContextObservedStats(
            entries=0,
            estimated_tokens=0,
            window=AgentContextObservedWindowStats(
                start_sequence=0,
                end_sequence=0,
                current_tokens=0,
            ),
        )

    def get_last_usage_marker(
        self,
        *,
        context_id: str,
    ) -> AgentContextUsageMarker | None:
        _ = context_id
        return None

    def estimate_window_tokens(self, *, context_id: str, start_sequence: int) -> int:
        entries = [
            entry
            for entry in self.entries
            if entry.context_id == context_id and entry.sequence >= start_sequence
        ]
        return sum(
            entry.delta_tokens
            for entry in entries
            if entry.delta_tokens is not None and entry.delta_tokens > 0
        )

    def estimate_delta_tokens(
        self,
        *,
        context_id: str,
        start_sequence: int,
        last_marker_sequence: int,
        payload: AgentContextPayload,
    ) -> int:
        _ = context_id, start_sequence, last_marker_sequence, payload
        large_delta_estimate = 1_000_000_000
        return large_delta_estimate

    def add_compact_delta_tokens(
        self,
        *,
        context_id: str,
        marker_sequence: int,
    ) -> None:
        _ = context_id, marker_sequence


class _FakeRunAgentStore:
    def get_agent(self, *, run_id: str, agent_id: str) -> RunAgent | None:
        _ = run_id, agent_id
        return None

    def attach_agent(self, *, run_id: str, agent_id: str, context_id: str) -> None:
        _ = run_id, agent_id, context_id


class _FakeAgentContextState:
    def get_state(self, *, context_id: str) -> AgentContextState:
        return AgentContextState(
            context_id=context_id,
            start_sequence=1,
            compacted_sequence=None,
            compaction_id=0,
        )


class _FakeProcessRunner:
    def __init__(
        self,
        *,
        output: ToolProcessOutput | None = None,
        poll_results: list[int | None] | None = None,
        start_error: str | None = None,
        wait_error: str | None = None,
    ) -> None:
        self.output = output or ToolProcessOutput(exit_code=0, stdout="", stderr="")
        self.poll_results = list(poll_results or [0])
        self.start_error = start_error
        self.wait_error = wait_error
        self.requests: list[ToolProcessRequest] = []
        self.terminated: list[ToolProcessHandle] = []

    def popen(self, request: ToolProcessRequest) -> ToolProcessStartResult:
        self.requests.append(request)
        if self.start_error is not None:
            return ToolProcessStartFailed(error=self.start_error)
        return ToolProcessStarted(handle=ToolProcessHandle(id="proc-1", pid=123))

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
        if self.wait_error is not None:
            return ToolProcessWaitFailed(error=self.wait_error)
        if request.interrupt is not None and request.interrupt.signal.is_interrupted(
            request.interrupt.run_id
        ):
            self.terminate(request.handle)
            return ToolProcessInterrupted()
        return ToolProcessCompleted(output=self.output)


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


def _event_output_config() -> AgentEventOutputConfig:
    return AgentEventOutputConfig(
        truncate=AgentEventOutputTruncateConfig(
            enabled=True,
            max_text_chars=600,
            max_json_chars=4000,
            max_array_items=20,
        ),
    )


@dataclass
class _FakeRuntimeEventStore(RuntimeEventStorePort):
    calls: list[dict[str, object]]

    def __init__(self) -> None:
        self.calls = []

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
