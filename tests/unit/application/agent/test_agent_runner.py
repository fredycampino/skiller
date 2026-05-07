import pytest

from skiller.application.agent.agent_runner import AgentRunner, AgentRunnerRequest
from skiller.application.agent.config.step_config_reader import AgentStepConfig
from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.application.ports.llm.llm_port import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
)
from skiller.application.use_cases.run.append_runtime_event import RuntimeEventType
from skiller.domain.agent.agent_context_model import AgentContextEntry, AgentContextEntryType
from skiller.domain.tool.tool_contract import ToolConfig, ToolResult, ToolResultStatus
from tests.helpers.agent_runner import build_agent_runner

pytestmark = pytest.mark.unit


class _FakeAgentContextStore:
    def __init__(self, entries: list[AgentContextEntry] | None = None) -> None:
        self.entries = list(entries or [])
        self.appended: list[dict[str, object]] = []

    def append_user_message(
        self,
        *,
        run_id: str,
        context_id: str,
        source_step_id: str,
        turn_id: str,
        text: str,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=run_id,
            context_id=context_id,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload={"type": "user_message", "text": text},
            source_step_id=source_step_id,
            idempotency_key=f"user:{source_step_id}:{turn_id}",
        )

    def append_assistant_message(
        self,
        *,
        run_id: str,
        context_id: str,
        source_step_id: str,
        turn_id: str,
        message_type: str,
        text: str,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=run_id,
            context_id=context_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={
                "type": "assistant_message",
                "turn_id": turn_id,
                "message_type": message_type,
                "text": text,
            },
            source_step_id=source_step_id,
            idempotency_key=f"assistant:{source_step_id}:{turn_id}",
        )

    def append_tool_call(
        self,
        *,
        run_id: str,
        context_id: str,
        source_step_id: str,
        turn_id: str,
        parent_sequence: int | None,
        tool_call_id: str,
        tool: str,
        args: dict[str, object],
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=run_id,
            context_id=context_id,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload={
                "type": "tool_call",
                "turn_id": turn_id,
                "parent_sequence": parent_sequence,
                "tool_call_id": tool_call_id,
                "tool": tool,
                "args": args,
            },
            source_step_id=source_step_id,
            idempotency_key=f"tool_call:{source_step_id}:{turn_id}:{tool_call_id}",
        )

    def append_tool_result(
        self,
        *,
        run_id: str,
        context_id: str,
        source_step_id: str,
        turn_id: str,
        parent_sequence: int | None,
        tool_call_id: str,
        tool: str,
        status: str,
        data: object,
        text: str | None,
        error: str | None,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=run_id,
            context_id=context_id,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload={
                "type": "tool_result",
                "turn_id": turn_id,
                "parent_sequence": parent_sequence,
                "tool_call_id": tool_call_id,
                "tool": tool,
                "status": status,
                "data": data,
                "text": text,
                "error": error,
            },
            source_step_id=source_step_id,
            idempotency_key=f"tool_result:{source_step_id}:{turn_id}:{tool_call_id}",
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

    def list_entries(self, *, run_id: str, context_id: str) -> list[AgentContextEntry]:
        return [
            entry
            for entry in self.entries
            if entry.run_id == run_id and entry.context_id == context_id
        ]


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
        self.execute_calls: list[AgentToolRequest] = []
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

    def execute(self, request: AgentToolRequest) -> ToolResult:
        self.execute_calls.append(request)
        if callable(self.execute_result):
            return self.execute_result(request)
        return self.execute_result


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


class _FakeAgentSteering:
    def __init__(self, consume_results: list[bool] | None = None) -> None:
        self.consume_results = list(consume_results or [])
        self.consume_calls: list[str] = []

    def enqueue(self, run_id: str, item) -> None:  # noqa: ANN001
        return None

    def consume_abort_turn(self, run_id: str) -> bool:
        self.consume_calls.append(run_id)
        if self.consume_results:
            return self.consume_results.pop(0)
        return False

    def pop_steering_messages(self, run_id: str) -> list[str]:
        return []


def _build_runner(
    *,
    context_store: _FakeAgentContextStore,
    llm: _FakeLLM,
    agent_steering: _FakeAgentSteering | None = None,
    tool_manager: _FakeToolManager | None = None,
    append_runtime_event_use_case: _FakeAppendRuntimeEventUseCase | None = None,
) -> AgentRunner:
    return build_agent_runner(
        agent_context_store=context_store,
        agent_steering=agent_steering,
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
    assert result.stop_reason == "final"
    assert result.response_model == "fake-model"


def test_agent_runner_interrupts_inside_tool_turn_executor() -> None:
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
    agent_steering = _FakeAgentSteering(consume_results=[True])
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        agent_steering=agent_steering,
        tool_manager=tool_manager,
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

    assert result.final_text == "Interrupted. Send another message if you want to continue."
    assert result.stop_reason == "interrupted"
    assert result.tool_call_count == 0
    assert tool_manager.execute_calls == []
    assert len(llm.calls) == 1
    assert llm.calls[0].messages == (
        LLMMessage.system("You are a support agent."),
        LLMMessage.user("Inspect the issue."),
    )
    assert [tool.name for tool in llm.calls[0].tools] == ["notify"]
    assert [item["entry_type"] for item in context_store.appended] == [
        AgentContextEntryType.USER_MESSAGE,
        AgentContextEntryType.USER_MESSAGE,
        AgentContextEntryType.ASSISTANT_MESSAGE,
    ]
    assert context_store.appended[1]["payload"] == {
        "type": "user_message",
        "text": "User interrupted the current agent turn.",
    }
    assert context_store.appended[2]["payload"] == {
        "type": "assistant_message",
        "turn_id": "turn-1",
        "message_type": "final",
        "text": "Interrupted. Send another message if you want to continue.",
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
    assert result.stop_reason == "success"
    assert tool_manager.get_tool_configs_calls == [["notify"]]
    assert tool_manager.execute_calls[0].tool == "notify"
    assert tool_manager.execute_calls[0].tool_call_id == "openai-call-1"
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
    assert tool_manager.execute_calls == []
    assert len(llm.calls) == 2
    assert llm.calls[1].messages[:2] == (
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hi"),
    )
    assert llm.calls[1].messages[2].content.startswith(
        "Invalid tool call arguments in step 'support_agent' for tool 'notify':"
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
    assert [request.tool_call_id for request in tool_manager.execute_calls] == [
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


def test_agent_runner_requires_tool_manager_when_tools_are_declared() -> None:
    runner = _build_runner(
        context_store=_FakeAgentContextStore(),
        llm=_FakeLLM(
            responses=[
                LLMResponse(
                    ok=True,
                    content="Done.",
                    model="fake",
                )
            ]
        ),
        tool_manager=None,
    )

    with pytest.raises(ValueError, match="requires tool_manager"):
        runner.execute(
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
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        tool_manager=_FakeToolManager(),
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

    assert result.final_text == (
        "I reached the turn limit before finishing. "
        "Send another message if you want me to continue."
    )
    assert result.stop_reason == "max_turns_exhausted"
    assert result.turn_count == 1
    assert context_store.appended[-2]["entry_type"] == AgentContextEntryType.USER_MESSAGE
    assert context_store.appended[-2]["payload"] == {
        "type": "user_message",
        "text": (
            "Agent reached max_turns without producing a final answer. "
            "Ask the user whether to continue."
        ),
    }
    assert context_store.appended[-1]["payload"] == {
        "type": "assistant_message",
        "turn_id": "turn-2",
        "message_type": "final",
        "text": (
            "I reached the turn limit before finishing. "
            "Send another message if you want me to continue."
        ),
    }
    assert llm.calls[0].messages == (
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hi"),
        LLMMessage.user(
            "Skiller warning: this is the last allowed turn. "
            "If you can finish, return the best final answer now. "
            "Otherwise, ask the user whether to continue. "
            "Do not plan more follow-up turns."
        ),
    )
    assert context_store.appended[1]["payload"] == {
        "type": "user_message",
        "text": (
            "Skiller warning: this is the last allowed turn. "
            "If you can finish, return the best final answer now. "
            "Otherwise, ask the user whether to continue. "
            "Do not plan more follow-up turns."
        ),
    }


def test_agent_runner_does_not_append_duplicate_last_turn_warning() -> None:
    warning = (
        "Skiller warning: this is the last allowed turn. "
        "If you can finish, return the best final answer now. "
        "Otherwise, ask the user whether to continue. "
        "Do not plan more follow-up turns."
    )
    context_store = _FakeAgentContextStore(
        entries=[
            AgentContextEntry(
                id="entry-1",
                run_id="run-1",
                context_id="thread-1",
                sequence=1,
                entry_type=AgentContextEntryType.USER_MESSAGE,
                payload={"type": "user_message", "text": "Hi"},
                source_step_id="support_agent",
                idempotency_key="user:support_agent:turn-1",
                created_at="2026-04-22T00:00:00Z",
            ),
            AgentContextEntry(
                id="entry-2",
                run_id="run-1",
                context_id="thread-1",
                sequence=2,
                entry_type=AgentContextEntryType.USER_MESSAGE,
                payload={"type": "user_message", "text": warning},
                source_step_id="support_agent",
                idempotency_key="user:support_agent:turn-2",
                created_at="2026-04-22T00:00:00Z",
            ),
        ]
    )
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                content="Done.",
                model="fake",
            )
        ]
    )
    runner = _build_runner(
        context_store=context_store,
        llm=llm,
        tool_manager=_FakeToolManager(),
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

    assert result.final_text == "Done."
    assert [item["payload"] for item in context_store.appended].count(
        {"type": "user_message", "text": warning}
    ) == 0
    assert llm.calls[0].messages[0] == LLMMessage.system("Be useful.")
    assert sum(
        1 for message in llm.calls[0].messages if message == LLMMessage.user(warning)
    ) == 1


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
    assert len(tool_manager.execute_calls) == 0
    assert len(llm.calls) == 1
    assert llm.calls[0].messages == (
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hi"),
    )
