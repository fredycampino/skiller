import pytest
from helpers.agent_config import agent_runner_config
from helpers.agent_runner import build_agent_runner

from skiller.application.agent.agent_runner import AgentRunner
from skiller.application.agent.runner_state import AgentRunnerRequest
from skiller.application.agent.tools.tool_manager import (
    PreparedTool,
    ToolPrepareFailure,
    ToolPrepareResult,
)
from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.application.tools.notify import NotifyTool
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextUsageMarker,
)
from skiller.domain.agent.agent_llm_provider_model import AgentFakeLLMModel
from skiller.domain.agent.agent_run_identity import AgentContext, AgentRun
from skiller.domain.agent.agent_run_model import AgentStopReason
from skiller.domain.agent.agent_stats_model import (
    AgentContextObservedStats,
    AgentContextObservedWindowStats,
)
from skiller.domain.agent.llm_model import (
    LLMAssistantMessage,
    LLMResponse,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
    LLMUsage,
    LLMUserMessage,
)
from skiller.domain.agent.llm_request import LLMRequest
from skiller.domain.event.event_model import (
    RuntimeEventPayload,
    RuntimeEventType,
    runtime_event_payload_to_dict,
)
from skiller.domain.run.steering_model import (
    SteeringAgentInterrupt,
    SteeringAgentMessage,
    SteeringItem,
    SteeringItemType,
)
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult

pytestmark = pytest.mark.unit

NOTIFY_TOOL_DEFINITION = NotifyTool()


class _FakeAgentContextStore:
    def __init__(self, entries: list[AgentContextEntry] | None = None) -> None:
        self.entries = list(entries or [])
        self.appended: list[dict[str, object]] = []
        self.window_calls: list[dict[str, object]] = []

    def append_user_message(
        self,
        *,
        context: AgentContext,
        text: str,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload={"type": "user_message", "text": text},
            source_step_id=context.agent_id,
        )

    def append_tool_calls_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None = None,
        delta_tokens: int = 0,
        window_start_sequence: int = 0,
        window_base: bool = False,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={
                "type": "assistant_message",
                "turn_id": turn_id,
                "message_type": AgentAssistantMessageType.TOOL_CALLS.value,
                "text": text,
            },
            usage=usage,
            message_type=AgentAssistantMessageType.TOOL_CALLS,
            window_start_sequence=window_start_sequence,
            delta_tokens=delta_tokens,
            window_base=window_base,
            source_step_id=context.agent_id,
        )

    def append_final_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None,
        delta_tokens: int,
        window_start_sequence: int,
        window_base: bool,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={
                "type": "assistant_message",
                "turn_id": turn_id,
                "message_type": AgentAssistantMessageType.FINAL.value,
                "text": text,
            },
            usage=usage,
            message_type=AgentAssistantMessageType.FINAL,
            window_start_sequence=window_start_sequence,
            delta_tokens=delta_tokens,
            window_base=window_base,
            source_step_id=context.agent_id,
        )

    def append_tool_call(
        self,
        *,
        context: AgentContext,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload={
                "type": "tool_call",
                "turn_id": tool_call.turn_id,
                "parent_sequence": tool_call.parent_sequence,
                "tool_call_id": tool_call.tool_call_id,
                "tool": tool_call.tool,
                "args": tool_call.args,
            },
            source_step_id=context.agent_id,
        )

    def append_tool_result(
        self,
        *,
        context: AgentContext,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry:
        result = tool_result.result
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
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
            source_step_id=context.agent_id,
        )

    def _append_entry(
        self,
        *,
        run_id: str,
        context_id: str,
        entry_type: AgentContextEntryType,
        payload: dict[str, object],
        usage: LLMUsage | None = None,
        message_type: AgentAssistantMessageType | None = None,
        window_start_sequence: int | None = None,
        delta_tokens: int | None = None,
        window_base: bool | None = None,
        source_step_id: str,
    ) -> AgentContextEntry:
        self.appended.append(
            {
                "run_id": run_id,
                "context_id": context_id,
                "entry_type": entry_type,
                "payload": payload,
                "message_type": message_type.value if message_type else None,
                "window_start_sequence": window_start_sequence,
                "delta_tokens": delta_tokens,
                "window_base": window_base,
                "source_step_id": source_step_id,
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
            window_start_sequence=window_start_sequence,
            delta_tokens=delta_tokens,
            window_base=window_base,
            source_step_id=source_step_id,
            created_at="2026-04-22T00:00:00Z",
        )
        self.entries.append(entry)
        return entry

    def list_entries(self, *, context_id: str) -> list[AgentContextEntry]:
        return [
            entry
            for entry in self.entries
            if entry.context_id == context_id
        ]

    def list_window_entries(
        self,
        *,
        context_id: str,
        window_width_tokens: int,
    ) -> list[AgentContextEntry]:
        self.window_calls.append(
            {
                "context_id": context_id,
                "window_width_tokens": window_width_tokens,
            }
        )
        return self.list_entries(context_id=context_id)

    def get_last_usage_marker(
        self,
        *,
        context_id: str,
    ) -> AgentContextUsageMarker | None:
        entries = [
            entry
            for entry in self.entries
            if entry.context_id == context_id
        ]
        for entry in reversed(entries):
            if entry.usage is None:
                continue
            if entry.usage.prompt_tokens is None:
                continue
            if entry.delta_tokens is None:
                continue
            if entry.window_start_sequence is None:
                continue
            if entry.window_base is None:
                continue
            return AgentContextUsageMarker(
                sequence=entry.sequence,
                prompt_tokens=entry.usage.prompt_tokens,
                delta_tokens=entry.delta_tokens,
                window_start_sequence=entry.window_start_sequence,
                window_base=entry.window_base,
            )
        return None

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

    def next_turn_id(self, *, context_id: str) -> str:
        entries = [
            entry
            for entry in self.entries
            if entry.context_id == context_id
        ]
        turn_entries = sum(
            1
            for entry in entries
            if entry.entry_type
            in {
                AgentContextEntryType.ASSISTANT_MESSAGE,
                AgentContextEntryType.TOOL_CALL,
            }
        )
        return f"turn-{turn_entries + 1}"


class _FakeLLM:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return self.responses.pop(0)


class _FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeToolManager:
    def __init__(self, execute_result: ToolResult | None = None) -> None:
        self.execute_prepared_calls: list[PreparedTool] = []
        self.execute_result = execute_result or ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"message": "ok"},
            text="ok",
            error=None,
        )

    def get_tools(self, allowed_tools: list[str]) -> list[_FakeTool]:
        return [_FakeTool(name=tool) for tool in allowed_tools]

    def prepare(self, request: AgentToolRequest) -> ToolPrepareResult:
        return ToolPrepareResult(
            ok=True,
            tool_name=request.tool,
            prepared=PreparedTool(
                name=request.tool,
                tool=_FakeTool(request.tool),
                request=request,
                config=request.runtime_config,
            ),
        )

    def execute_prepared(self, prepared: PreparedTool) -> ToolResult:
        request = prepared.request
        if not isinstance(request, AgentToolRequest):
            raise AssertionError("expected AgentToolRequest")
        self.execute_prepared_calls.append(prepared)
        return self.execute_result


class _ExceptionPrepareToolManager:
    def prepare(self, request: AgentToolRequest) -> ToolPrepareResult:
        return ToolPrepareResult(
            ok=False,
            tool_name=request.tool,
            error=ToolPrepareFailure.REQUEST_EXCEPTION,
            error_message="request boom",
        )

    def execute_prepared(self, prepared: PreparedTool) -> ToolResult:
        _ = prepared
        raise AssertionError("execute_prepared should not be called")


class _FakeAppendRuntimeEventUseCase:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def execute(
        self,
        run_id: str,
        *,
        event_type: RuntimeEventType,
        payload: RuntimeEventPayload | dict[str, object] | None = None,
        step_id: str | None = None,
        step_type=None,  # noqa: ANN001
        agent_sequence: int | None = None,
        execution=None,  # noqa: ANN001
        next_step_id: str | None = None,
        error: str | None = None,
    ) -> None:
        self.calls.append(
            {
                "run_id": run_id,
                "event_type": event_type,
                "payload": (
                    runtime_event_payload_to_dict(payload)
                    if payload is not None
                    else None
                ),
                "step_id": step_id,
                "step_type": step_type,
                "agent_sequence": agent_sequence,
                "execution": execution,
                "next_step_id": next_step_id,
                "error": error,
            }
        )


class _FakeSteering:
    def __init__(self, consume_results: list[bool] | None = None) -> None:
        self.consume_results = list(consume_results or [])
        self.pop_calls: list[tuple[str, object]] = []

    def append(self, run_id: str, item: SteeringItem) -> None:
        return None

    def pop(self, run_id: str, item_type: SteeringItemType) -> list[SteeringItem]:
        self.pop_calls.append((run_id, item_type))
        if item_type is SteeringAgentInterrupt and self.consume_results:
            if self.consume_results.pop(0):
                return [SteeringAgentInterrupt()]
            return []
        if item_type is SteeringAgentMessage:
            return []
        return []


def _build_runner(
    *,
    context_store: _FakeAgentContextStore,
    llm: _FakeLLM,
    steering: _FakeSteering | None = None,
    tool_manager: _FakeToolManager | None = None,
    append_runtime_event_use_case: _FakeAppendRuntimeEventUseCase | None = None,
) -> AgentRunner:
    return build_agent_runner(
        agent_context_store=context_store,
        steering=steering,
        llm=llm,
        tool_manager=tool_manager,
        append_runtime_event_use_case=append_runtime_event_use_case,
    )


def test_agent_runner_returns_final_text_without_tools() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[LLMResponse(ok=True, content="Hello back.", model=AgentFakeLLMModel.MODEL1)]
    )
    runner = _build_runner(context_store=context_store, llm=llm)

    result = runner.execute(
        AgentRunnerRequest(
            agent=AgentRun(run_id="run-1", agent_id="support_agent"),
            config=agent_runner_config(
                system="Be useful.",
                task="Hi",
                max_turns=1,
                tools=(),
            ),
        )
    )

    assert result.final_text == "Hello back."
    assert result.turn_count == 1
    assert result.tool_call_count == 0
    assert result.finish == AgentStopReason.FINAL
    assert result.response_model == "model1"
    assert context_store.window_calls == [
        {
            "context_id": result.context_id,
            "window_width_tokens": 80_000,
        }
    ]


def test_agent_runner_interrupts_inside_tool_execution() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                content=None,
                model=AgentFakeLLMModel.MODEL1,
                tool_calls=(
                    LLMToolCall(
                        id="call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"hello"}',
                        ),
                    ),
                ),
            )
        ]
    )
    tool_manager = _FakeToolManager()
    steering = _FakeSteering(consume_results=[True])
    append_event = _FakeAppendRuntimeEventUseCase()
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        steering=steering,
        tool_manager=tool_manager,
        append_runtime_event_use_case=append_event,
    )

    result = runner.execute(
        AgentRunnerRequest(
            agent=AgentRun(run_id="run-1", agent_id="support_agent"),
            config=agent_runner_config(
                system="You are a support agent.",
                task="Inspect the issue.",
                max_turns=3,
                tools=(NOTIFY_TOOL_DEFINITION,),
                max_tool_calls=5,
            ),
        )
    )

    assert result.final_text is None
    assert result.finish == AgentStopReason.INTERRUPTED
    assert result.tool_call_count == 0
    assert tool_manager.execute_prepared_calls == []
    assert len(llm.calls) == 1
    assert llm.calls[0].messages == (
        LLMSystemMessage("You are a support agent."),
        LLMUserMessage("Inspect the issue."),
    )
    assert [tool.name for tool in llm.calls[0].tools] == ["notify"]
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.USER_MESSAGE,
        AgentContextEntryType.USER_MESSAGE,
    ]
    assert context_store.appended[1]["payload"] == {
        "type": "user_message",
        "text": "[Skiller] User interrupted the current tool turn.",
    }
    assert append_event.calls[-1]["event_type"] == RuntimeEventType.AGENT_INTERRUPTED
    assert append_event.calls[-1]["payload"] == {
        "turn_id": "turn-1",
        "stop_reason": "interrupted",
    }
    assert append_event.calls[-1]["step_id"] == "support_agent"
    assert append_event.calls[-1]["step_type"] == "agent"

def test_agent_runner_executes_tool_and_emits_events() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                model=AgentFakeLLMModel.MODEL1,
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"hello"}',
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            ),
            LLMResponse(
                ok=True,
                content="Done.",
                model=AgentFakeLLMModel.MODEL1,
                usage=LLMUsage(prompt_tokens=100, completion_tokens=25, total_tokens=125),
            ),
        ]
    )
    tool_manager = _FakeToolManager(
        execute_result=ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"message": "sent"},
            text="sent",
            error=None,
        )
    )
    append_event = _FakeAppendRuntimeEventUseCase()
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        tool_manager=tool_manager,
        append_runtime_event_use_case=append_event,
    )

    result = runner.execute(
        AgentRunnerRequest(
            agent=AgentRun(run_id="run-1", agent_id="support_agent"),
            config=agent_runner_config(
                system="Be useful.",
                task="Hi",
                max_turns=3,
                tools=(NOTIFY_TOOL_DEFINITION,),
                max_tool_calls=5,
            ),
        )
    )

    assert result.final_text == "Done."
    assert result.turn_count == 2
    assert result.tool_call_count == 1
    assert result.finish == AgentStopReason.FINAL
    assert result.usage == LLMUsage(
        prompt_tokens=100,
        completion_tokens=25,
        total_tokens=125,
        provider="fake",
        model=AgentFakeLLMModel.MODEL1,
    )
    executed_request = tool_manager.execute_prepared_calls[0].request
    assert isinstance(executed_request, AgentToolRequest)
    assert executed_request.tool == "notify"
    assert executed_request.tool_call_id == "openai-call-1"
    assert llm.calls[0].messages == (
        LLMSystemMessage("Be useful."),
        LLMUserMessage("Hi"),
    )
    assert [tool.name for tool in llm.calls[0].tools] == ["notify"]
    assert llm.calls[1].messages == (
        LLMSystemMessage("Be useful."),
        LLMUserMessage("Hi"),
        LLMAssistantMessage(
            tool_calls=(
                LLMToolCall(
                    id="openai-call-1",
                    function=LLMToolCallFunction(
                        name="notify",
                        arguments_json='{"message": "hello"}',
                    ),
                ),
            )
        ),
        LLMToolMessage(
            '{"data": {"message": "sent"}, "status": "COMPLETED", "tool": "notify"}',
            tool_call_id="openai-call-1",
        ),
    )
    assert [call["event_type"] for call in append_event.calls] == [
        RuntimeEventType.AGENT_TOOL_CALL,
        RuntimeEventType.AGENT_TOOL_RESULT,
        RuntimeEventType.AGENT_FINAL_ASSISTANT_MESSAGE,
    ]
    final_payload = append_event.calls[-1]["payload"]
    assert isinstance(final_payload, dict)
    assert final_payload["body"]["total_tokens"] == 125


def test_agent_runner_preserves_assistant_content_with_native_tool_call() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                content="I should send a notification.",
                model=AgentFakeLLMModel.MODEL1,
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message": "hello"}',
                        ),
                    ),
                ),
                finish_reason="tool_calls",
                usage=LLMUsage(prompt_tokens=50, completion_tokens=10, total_tokens=60),
            ),
            LLMResponse(
                ok=True,
                content="Done.",
                model=AgentFakeLLMModel.MODEL1,
                usage=LLMUsage(prompt_tokens=100, completion_tokens=25, total_tokens=125),
            ),
        ]
    )
    tool_manager = _FakeToolManager(
        execute_result=ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"message": "sent"},
            text="sent",
            error=None,
        )
    )
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        tool_manager=tool_manager,
    )

    result = runner.execute(
        AgentRunnerRequest(
            agent=AgentRun(run_id="run-1", agent_id="support_agent"),
            config=agent_runner_config(
                system="Be useful.",
                task="Hi",
                max_turns=3,
                tools=(NOTIFY_TOOL_DEFINITION,),
                max_tool_calls=5,
            ),
        )
    )

    assert result.final_text == "Done."
    assert result.turn_count == 2
    assert result.tool_call_count == 1
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.USER_MESSAGE,
        AgentContextEntryType.ASSISTANT_MESSAGE,
        AgentContextEntryType.TOOL_CALL,
        AgentContextEntryType.TOOL_RESULT,
        AgentContextEntryType.ASSISTANT_MESSAGE,
    ]
    assert context_store.appended[1]["payload"]["text"] == "I should send a notification."
    assert llm.calls[1].messages == (
        LLMSystemMessage("Be useful."),
        LLMUserMessage("Hi"),
        LLMAssistantMessage(
            "I should send a notification.",
            tool_calls=(
                LLMToolCall(
                    id="openai-call-1",
                    function=LLMToolCallFunction(
                        name="notify",
                        arguments_json='{"message": "hello"}',
                    ),
                ),
            ),
        ),
        LLMToolMessage(
            '{"data": {"message": "sent"}, "status": "COMPLETED", "tool": "notify"}',
            tool_call_id="openai-call-1",
        ),
    )

def test_agent_runner_reprompts_when_native_tool_call_arguments_are_invalid() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                model=AgentFakeLLMModel.MODEL1,
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message": "hello"',
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            ),
            LLMResponse(
                ok=True,
                content="Done.",
                model=AgentFakeLLMModel.MODEL1,
            ),
        ]
    )
    tool_manager = _FakeToolManager()
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        tool_manager=tool_manager,
    )

    result = runner.execute(
        AgentRunnerRequest(
            agent=AgentRun(run_id="run-1", agent_id="support_agent"),
            config=agent_runner_config(
                system="Be useful.",
                task="Hi",
                max_turns=3,
                tools=(NOTIFY_TOOL_DEFINITION,),
                max_tool_calls=5,
            ),
        )
    )

    assert result.final_text == "Done."
    assert result.turn_count == 2
    assert result.tool_call_count == 0
    assert tool_manager.execute_prepared_calls == []
    assert len(llm.calls) == 2
    assert llm.calls[1].messages[:2] == (
        LLMSystemMessage("Be useful."),
        LLMUserMessage("Hi"),
    )
    assert llm.calls[1].messages[2].content.startswith(
        "[Skiller] Invalid tool call arguments in step 'support_agent' for tool 'notify':"
    )
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.USER_MESSAGE,
        AgentContextEntryType.USER_MESSAGE,
        AgentContextEntryType.ASSISTANT_MESSAGE,
    ]


def test_agent_runner_waits_when_reaching_max_turns_without_final_answer() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"hello"}',
                        ),
                    ),
                ),
                model=AgentFakeLLMModel.MODEL1,
            )
        ]
    )
    append_event = _FakeAppendRuntimeEventUseCase()
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        tool_manager=_FakeToolManager(),
        append_runtime_event_use_case=append_event,
    )

    result = runner.execute(
        AgentRunnerRequest(
            agent=AgentRun(run_id="run-1", agent_id="support_agent"),
            config=agent_runner_config(
                system="Be useful.",
                task="Hi",
                max_turns=1,
                tools=(NOTIFY_TOOL_DEFINITION,),
            ),
        )
    )

    assert result.final_text is None
    assert result.finish == AgentStopReason.MAX_TURNS_EXHAUSTED
    assert result.turn_count == 1
    assert context_store.appended[-1]["entry_type"] == AgentContextEntryType.USER_MESSAGE
    assert context_store.appended[-1]["payload"] == {
        "type": "user_message",
        "text": "[Skiller] max_turns exhausted before a final answer.",
    }
    assert llm.calls[0].messages == (
        LLMSystemMessage("Be useful."),
        LLMUserMessage("Hi"),
        LLMUserMessage(
            "[Skiller] Last allowed turn. "
            "If you can finish, return the final answer now. "
            "Otherwise stop and wait for the user to continue."
        ),
    )
    assert context_store.appended[1]["payload"] == {
        "type": "user_message",
        "text": (
            "[Skiller] Last allowed turn. "
            "If you can finish, return the final answer now. "
            "Otherwise stop and wait for the user to continue."
        ),
    }
    assert append_event.calls[-1]["event_type"] == (
        RuntimeEventType.AGENT_MAX_TURNS_EXHAUSTED
    )
    assert append_event.calls[-1]["payload"] == {
        "turn_id": "turn-2",
        "stop_reason": "max_turns_exhausted",
    }
    assert append_event.calls[-1]["step_id"] == "support_agent"
    assert append_event.calls[-1]["step_type"] == "agent"


def test_agent_runner_uses_plain_text_final_answer_with_tools_enabled() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                content="Done.",
                model=AgentFakeLLMModel.MODEL1,
            )
        ]
    )
    tool_manager = _FakeToolManager()
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        tool_manager=tool_manager,
    )

    result = runner.execute(
        AgentRunnerRequest(
            agent=AgentRun(run_id="run-1", agent_id="support_agent"),
            config=agent_runner_config(
                system="Be useful.",
                task="Hi",
                max_turns=4,
                tools=(NOTIFY_TOOL_DEFINITION,),
            ),
        )
    )

    assert result.final_text == "Done."
    assert result.turn_count == 1
    assert result.tool_call_count == 0
    assert len(tool_manager.execute_prepared_calls) == 0
    assert len(llm.calls) == 1
    assert llm.calls[0].messages == (
        LLMSystemMessage("Be useful."),
        LLMUserMessage("Hi"),
    )


def test_agent_runner_returns_llm_request_failed_finish() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=False,
                model=AgentFakeLLMModel.MODEL1,
                error="invalid params",
                error_code="2013",
            )
        ]
    )
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        tool_manager=None,
    )

    result = runner.execute(
        AgentRunnerRequest(
            agent=AgentRun(run_id="run-1", agent_id="support_agent"),
            config=agent_runner_config(
                system="Be useful.",
                task="Hi",
                max_turns=3,
                tools=(),
            ),
        )
    )

    assert result.final_text is None
    assert result.finish == AgentStopReason.LLM_REQUEST_FAILED
    assert result.error == (
        "Agent 'support_agent' LLM request failed: invalid params (error_code=2013)"
    )


def test_agent_runner_returns_tool_execution_failed_finish() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                content=None,
                model=AgentFakeLLMModel.MODEL1,
                tool_calls=(
                    LLMToolCall(
                        id="call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"hello"}',
                        ),
                    ),
                ),
            )
        ]
    )
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        tool_manager=_ExceptionPrepareToolManager(),
    )

    result = runner.execute(
        AgentRunnerRequest(
            agent=AgentRun(run_id="run-1", agent_id="support_agent"),
            config=agent_runner_config(
                system="Be useful.",
                task="Hi",
                max_turns=3,
                tools=(NOTIFY_TOOL_DEFINITION,),
            ),
        )
    )

    assert result.final_text is None
    assert result.finish == AgentStopReason.TOOL_EXECUTION_FAILED
    assert result.error == "request boom"
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.USER_MESSAGE,
        AgentContextEntryType.TOOL_CALL,
    ]


def test_agent_runner_returns_invalid_final_message_finish() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                content="   ",
                model=AgentFakeLLMModel.MODEL1,
            )
        ]
    )
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        tool_manager=None,
    )

    result = runner.execute(
        AgentRunnerRequest(
            agent=AgentRun(run_id="run-1", agent_id="support_agent"),
            config=agent_runner_config(
                system="Be useful.",
                task="Hi",
                max_turns=3,
                tools=(),
            ),
        )
    )

    assert result.final_text is None
    assert result.finish == AgentStopReason.INVALID_FINAL_MESSAGE
    assert result.error == "Agent step 'support_agent' returned no final answer"
