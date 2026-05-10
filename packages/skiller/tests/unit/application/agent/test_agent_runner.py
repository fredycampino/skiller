import pytest
from helpers.agent_runner import build_agent_runner
from skiller.application.agent.agent_runner import AgentRunner, AgentRunnerRequest
from skiller.application.agent.config.step_config_reader import AgentStepConfig
from skiller.application.agent.tools.tool_manager import (
    PreparedTool,
    ToolPrepareFailure,
    ToolPrepareResult,
)
from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.application.use_cases.run.append_runtime_event import RuntimeEventType
from skiller.domain.agent.agent_context_model import (
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextToolCall,
    AgentContextToolResult,
)
from skiller.domain.agent.agent_run_model import AgentRunnerFinish
from skiller.domain.agent.llm_model import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
)
from skiller.domain.run.steering_model import (
    SteeringAgentInterrupt,
    SteeringAgentMessage,
    SteeringItem,
    SteeringItemType,
)
from skiller.domain.tool.tool_contract import ToolConfig, ToolResult, ToolResultStatus

pytestmark = pytest.mark.unit


class _FakeAgentContextStore:
    def __init__(self, entries: list[AgentContextEntry] | None = None) -> None:
        self.entries = list(entries or [])
        self.appended: list[dict[str, object]] = []

    def append_user_message(
        self,
        *,
        scope,
        turn_id: str,
        text: str,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=scope.run_id,
            context_id=scope.context_id,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload={"type": "user_message", "text": text},
            source_step_id=scope.agent_id,
            idempotency_key=f"user:{scope.agent_id}:{turn_id}",
        )

    def append_assistant_message(
        self,
        *,
        scope,
        turn_id: str,
        message_type: str,
        text: str,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=scope.run_id,
            context_id=scope.context_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={
                "type": "assistant_message",
                "turn_id": turn_id,
                "message_type": message_type,
                "text": text,
            },
            source_step_id=scope.agent_id,
            idempotency_key=f"assistant:{scope.agent_id}:{turn_id}",
        )

    def append_tool_call(
        self,
        *,
        scope,
        turn_id: str,
        parent_sequence: int | None,
        tool_call: AgentContextToolCall,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=scope.run_id,
            context_id=scope.context_id,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload={
                "type": "tool_call",
                "turn_id": turn_id,
                "parent_sequence": parent_sequence,
                "tool_call_id": tool_call.id,
                "tool": tool_call.tool,
                "args": tool_call.args,
            },
            source_step_id=scope.agent_id,
            idempotency_key=f"tool_call:{scope.agent_id}:{turn_id}:{tool_call.id}",
        )

    def append_tool_result(
        self,
        *,
        scope,
        turn_id: str,
        parent_sequence: int | None,
        tool_result: AgentContextToolResult,
    ) -> AgentContextEntry:
        result = tool_result.result
        return self._append_entry(
            run_id=scope.run_id,
            context_id=scope.context_id,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload={
                "type": "tool_result",
                "turn_id": turn_id,
                "parent_sequence": parent_sequence,
                "tool_call_id": tool_result.tool_call_id,
                "tool": result.name,
                "status": result.status.value,
                "data": result.data,
                "text": result.text,
                "error": result.error,
            },
            source_step_id=scope.agent_id,
            idempotency_key=f"tool_result:{scope.agent_id}:{turn_id}:{tool_result.tool_call_id}",
        )

    def _append_entry(
        self,
        *,
        run_id: str,
        context_id: str,
        entry_type: AgentContextEntryType,
        payload: dict[str, object],
        source_step_id: str,
        idempotency_key: str,
    ) -> AgentContextEntry:
        self.appended.append(
            {
                "run_id": run_id,
                "context_id": context_id,
                "entry_type": entry_type,
                "payload": payload,
                "source_step_id": source_step_id,
                "idempotency_key": idempotency_key,
            }
        )
        entry = AgentContextEntry(
            id=f"entry-{len(self.entries) + 1}",
            run_id=run_id,
            context_id=context_id,
            sequence=len(self.entries) + 1,
            entry_type=entry_type,
            payload=payload,
            source_step_id=source_step_id,
            idempotency_key=idempotency_key,
            created_at="2026-04-22T00:00:00Z",
        )
        self.entries.append(entry)
        return entry

    def list_entries(self, *, scope) -> list[AgentContextEntry]:
        return [
            entry
            for entry in self.entries
            if entry.run_id == scope.run_id and entry.context_id == scope.context_id
        ]

    def next_turn_id(self, *, scope) -> str:
        entries = self.list_entries(scope=scope)
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
        self.get_tool_configs_calls: list[list[str]] = []
        self.execute_prepared_calls: list[PreparedTool] = []
        self.execute_result = execute_result or ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"message": "ok"},
            text="ok",
            error=None,
        )

    def get_tool_configs(self, allowed_tools: list[str]) -> list[ToolConfig]:
        self.get_tool_configs_calls.append(list(allowed_tools))
        return [
            ToolConfig(
                name=tool,
                description=f"Fake {tool} tool",
                parameters_schema={},
            )
            for tool in allowed_tools
        ]

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
            ),
        )

    def execute_prepared(self, prepared: PreparedTool) -> ToolResult:
        request = prepared.request
        if not isinstance(request, AgentToolRequest):
            raise AssertionError("expected AgentToolRequest")
        self.execute_prepared_calls.append(prepared)
        if callable(self.execute_result):
            return self.execute_result(request)
        return self.execute_result


class _ExceptionPrepareToolManager:
    def get_tool_configs(self, allowed_tools: list[str]) -> list[ToolConfig]:
        return [
            ToolConfig(
                name=tool,
                description=f"Fake {tool} tool",
                parameters_schema={},
            )
            for tool in allowed_tools
        ]

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
        payload: dict[str, object] | None = None,
        step_id: str | None = None,
        step_type=None,  # noqa: ANN001
        execution=None,  # noqa: ANN001
        next_step_id: str | None = None,
        error: str | None = None,
    ) -> None:
        self.calls.append(
            {
                "run_id": run_id,
                "event_type": event_type,
                "payload": payload,
                "step_id": step_id,
                "step_type": step_type,
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
        responses=[LLMResponse(ok=True, content="Hello back.", model="fake-model")]
    )
    runner = _build_runner(context_store=context_store, llm=llm)

    result = runner.execute(
        AgentRunnerRequest(
            run_id="run-1",
            step_id="support_agent",
            config=AgentStepConfig(
                system="Be useful.",
                task="Hi",
                context_id="thread-1",
                max_turns=1,
                tools=[],
            ),
        )
    )

    assert result.final_text == "Hello back."
    assert result.turn_count == 1
    assert result.tool_call_count == 0
    assert result.finish == AgentRunnerFinish.FINAL
    assert result.response_model == "fake-model"


def test_agent_runner_interrupts_inside_tool_execution() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                content=None,
                model="fake-model",
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
            run_id="run-1",
            step_id="support_agent",
            config=AgentStepConfig(
                system="You are a support agent.",
                task="Inspect the issue.",
                context_id="thread-1",
                max_turns=3,
                tools=["notify"],
                max_tool_calls=5,
            ),
        )
    )

    assert result.final_text is None
    assert result.finish == AgentRunnerFinish.INTERRUPTED
    assert result.tool_call_count == 0
    assert tool_manager.execute_prepared_calls == []
    assert len(llm.calls) == 1
    assert llm.calls[0].messages == (
        LLMMessage.system("You are a support agent."),
        LLMMessage.user("Inspect the issue."),
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
        "step": "support_agent",
        "step_type": "agent",
        "turn_id": "turn-1",
        "stop_reason": "interrupted",
    }

def test_agent_runner_executes_tool_and_emits_events() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                model="fake",
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
                model="fake",
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
            run_id="run-1",
            step_id="support_agent",
                config=AgentStepConfig(
                    system="Be useful.",
                    task="Hi",
                    context_id="thread-1",
                    max_turns=3,
                    tools=["notify"],
                    max_tool_calls=5,
                ),
            )
        )

    assert result.final_text == "Done."
    assert result.turn_count == 2
    assert result.tool_call_count == 1
    assert result.finish == AgentRunnerFinish.FINAL
    assert tool_manager.get_tool_configs_calls == [["notify"]]
    executed_request = tool_manager.execute_prepared_calls[0].request
    assert isinstance(executed_request, AgentToolRequest)
    assert executed_request.tool == "notify"
    assert executed_request.tool_call_id == "openai-call-1"
    assert llm.calls[0].messages == (
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hi"),
    )
    assert [tool.name for tool in llm.calls[0].tools] == ["notify"]
    assert llm.calls[1].messages == (
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hi"),
        LLMMessage.assistant(
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
        LLMMessage.tool("sent", tool_call_id="openai-call-1"),
    )
    assert append_event.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.AGENT_TOOL_CALL,
            "payload": {
                "step": "support_agent",
                "step_type": "agent",
                "turn_id": "turn-1",
                "sequence": 2,
                "tool_call_id": "openai-call-1",
                "tool": "notify",
                "args": {"message": "hello"},
            },
            "step_id": None,
            "step_type": None,
            "execution": None,
            "next_step_id": None,
            "error": None,
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.AGENT_TOOL_RESULT,
            "payload": {
                "step": "support_agent",
                "step_type": "agent",
                "turn_id": "turn-1",
                "sequence": 3,
                "tool_call_id": "openai-call-1",
                "tool": "notify",
                "context_ref": "agent_context:entry-3",
                "output": {
                    "text": "sent",
                    "value": {"message": "sent"},
                    "body_ref": None,
                },
            },
            "step_id": None,
            "step_type": None,
            "execution": None,
            "next_step_id": None,
            "error": None,
        },
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.AGENT_ASSISTANT_MESSAGE,
            "payload": {
                "step": "support_agent",
                "step_type": "agent",
                "turn_id": "turn-2",
                "sequence": 4,
                "message_type": "final",
                "text": "Done.",
            },
            "step_id": None,
            "step_type": None,
            "execution": None,
            "next_step_id": None,
            "error": None,
        },
    ]


def test_agent_runner_preserves_assistant_content_with_native_tool_call() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                content="I should send a notification.",
                model="fake",
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
            ),
            LLMResponse(ok=True, content="Done.", model="fake"),
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
            run_id="run-1",
            step_id="support_agent",
            config=AgentStepConfig(
                system="Be useful.",
                task="Hi",
                context_id="thread-1",
                max_turns=3,
                tools=["notify"],
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
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hi"),
        LLMMessage.assistant(
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
        LLMMessage.tool("sent", tool_call_id="openai-call-1"),
    )
    assert [item["event_type"] for item in append_event.calls] == [
        RuntimeEventType.AGENT_ASSISTANT_MESSAGE,
        RuntimeEventType.AGENT_TOOL_CALL,
        RuntimeEventType.AGENT_TOOL_RESULT,
        RuntimeEventType.AGENT_ASSISTANT_MESSAGE,
    ]
    assert append_event.calls[0]["payload"] == {
        "step": "support_agent",
        "step_type": "agent",
        "turn_id": "turn-1",
        "sequence": 2,
        "message_type": "tool_calls",
        "text": "I should send a notification.",
    }
    assert append_event.calls[1]["payload"]["parent_sequence"] == 2
    assert append_event.calls[2]["payload"]["parent_sequence"] == 2
    assert append_event.calls[3]["payload"] == {
        "step": "support_agent",
        "step_type": "agent",
        "turn_id": "turn-3",
        "sequence": 5,
        "message_type": "final",
        "text": "Done.",
    }


def test_agent_runner_reprompts_when_native_tool_call_arguments_are_invalid() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                model="fake",
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
                model="fake",
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
            run_id="run-1",
            step_id="support_agent",
            config=AgentStepConfig(
                system="Be useful.",
                task="Hi",
                context_id="thread-1",
                max_turns=3,
                tools=["notify"],
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
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hi"),
    )
    assert llm.calls[1].messages[2].content.startswith(
        "[Skiller] Invalid tool call arguments in step 'support_agent' for tool 'notify':"
    )
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.USER_MESSAGE,
        AgentContextEntryType.USER_MESSAGE,
        AgentContextEntryType.ASSISTANT_MESSAGE,
    ]


def test_agent_runner_executes_multiple_tool_calls_in_one_turn() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                model="fake",
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
                finish_reason="tool_calls",
            ),
            LLMResponse(
                ok=True,
                content="Done.",
                model="fake",
            ),
        ]
    )

    def execute_result(request: AgentToolRequest) -> ToolResult:
        return ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"message": request.args["message"]},
            text=str(request.args["message"]),
            error=None,
        )

    tool_manager = _FakeToolManager(execute_result=execute_result)
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        tool_manager=tool_manager,
    )

    result = runner.execute(
        AgentRunnerRequest(
            run_id="run-1",
            step_id="support_agent",
            config=AgentStepConfig(
                system="Be useful.",
                task="Hi",
                context_id="thread-1",
                max_turns=3,
                tools=["notify"],
                max_tool_calls=5,
            ),
        )
    )

    assert result.final_text == "Done."
    assert result.turn_count == 2
    assert result.tool_call_count == 2
    executed_requests = [
        prepared.request for prepared in tool_manager.execute_prepared_calls
    ]
    assert all(isinstance(request, AgentToolRequest) for request in executed_requests)
    assert [request.tool_call_id for request in executed_requests] == [
        "call-1",
        "call-2",
    ]
    assert llm.calls[1].messages == (
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hi"),
        LLMMessage.assistant(
            tool_calls=(
                LLMToolCall(
                    id="call-1",
                    function=LLMToolCallFunction(
                        name="notify",
                        arguments_json='{"message": "hello"}',
                    ),
                ),
                LLMToolCall(
                    id="call-2",
                    function=LLMToolCallFunction(
                        name="notify",
                        arguments_json='{"message": "world"}',
                    ),
                ),
            )
        ),
        LLMMessage.tool("hello", tool_call_id="call-1"),
        LLMMessage.tool("world", tool_call_id="call-2"),
    )


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
                model="fake",
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
            run_id="run-1",
            step_id="support_agent",
            config=AgentStepConfig(
                system="Be useful.",
                task="Hi",
                context_id="thread-1",
                max_turns=1,
                tools=["notify"],
            ),
        )
    )

    assert result.final_text is None
    assert result.finish == AgentRunnerFinish.MAX_TURNS_EXHAUSTED
    assert result.turn_count == 1
    assert context_store.appended[-1]["entry_type"] == AgentContextEntryType.USER_MESSAGE
    assert context_store.appended[-1]["payload"] == {
        "type": "user_message",
        "text": "[Skiller] max_turns exhausted before a final answer.",
    }
    assert llm.calls[0].messages == (
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hi"),
        LLMMessage.user(
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
        "step": "support_agent",
        "step_type": "agent",
        "turn_id": "turn-2",
        "stop_reason": "max_turns_exhausted",
    }


def test_agent_runner_uses_plain_text_final_answer_with_tools_enabled() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                content="Done.",
                model="fake",
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
            run_id="run-1",
            step_id="support_agent",
            config=AgentStepConfig(
                system="Be useful.",
                task="Hi",
                context_id="thread-1",
                max_turns=4,
                tools=["notify"],
            ),
        )
    )

    assert result.final_text == "Done."
    assert result.turn_count == 1
    assert result.tool_call_count == 0
    assert len(tool_manager.execute_prepared_calls) == 0
    assert len(llm.calls) == 1
    assert llm.calls[0].messages == (
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hi"),
    )


def test_agent_runner_returns_llm_request_failed_finish() -> None:
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=False,
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
            run_id="run-1",
            step_id="support_agent",
            config=AgentStepConfig(
                system="Be useful.",
                task="Hi",
                context_id="thread-1",
                max_turns=3,
                tools=[],
            ),
        )
    )

    assert result.final_text is None
    assert result.finish == AgentRunnerFinish.LLM_REQUEST_FAILED
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
                model="fake-model",
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
            run_id="run-1",
            step_id="support_agent",
            config=AgentStepConfig(
                system="Be useful.",
                task="Hi",
                context_id="thread-1",
                max_turns=3,
                tools=["notify"],
            ),
        )
    )

    assert result.final_text is None
    assert result.finish == AgentRunnerFinish.TOOL_EXECUTION_FAILED
    assert result.error == "request boom"
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.USER_MESSAGE,
        AgentContextEntryType.TOOL_CALL,
    ]
