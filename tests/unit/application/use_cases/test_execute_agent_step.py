import pytest

from skiller.application.agent.config.event_output_sanitizer import (
    AgentEventOutputPolicy,
    AgentEventOutputSanitizer,
)
from skiller.application.agent.config.step_config_reader import AGENT_RUNTIME_SYSTEM
from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.application.ports.llm.llm_port import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
)
from skiller.application.use_cases.execute.execute_agent_step import (
    ExecuteAgentStepUseCase,
)
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.application.use_cases.run.append_runtime_event import RuntimeEventType
from skiller.application.use_cases.shared.step_execution_result import StepExecutionStatus
from skiller.domain.agent.agent_context_model import AgentContextEntry, AgentContextEntryType
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.step_execution_model import AgentOutput
from skiller.domain.step.step_type import StepType
from skiller.domain.tool.tool_contract import ToolConfig, ToolResult, ToolResultStatus
from tests.helpers.agent_runner import build_agent_runner

pytestmark = pytest.mark.unit


def _assert_system_message_contains(
    message: LLMMessage,
    *,
    step_system: str,
) -> None:
    assert message.role.value == "system"
    assert AGENT_RUNTIME_SYSTEM in (message.content or "")
    assert step_system in (message.content or "")


class _FakeStore:
    def __init__(self) -> None:
        self.updated: list[dict[str, object]] = []

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        self.updated.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )


class _FakeAgentContextStore:
    def __init__(self, entries: list[AgentContextEntry] | None = None) -> None:
        self.entries = list(entries or [])
        self.appended: list[dict[str, object]] = []

    def init_db(self) -> None:
        return None

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
    def __init__(
        self,
        response: object | None = None,
        responses: list[object] | None = None,
    ) -> None:
        self.response = response or {"ok": True, "content": "Hello back.", "model": "fake"}
        self.responses = list(responses or [])
        self.calls: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        if self.responses:
            return self._to_llm_response(self.responses.pop(0))
        return self._to_llm_response(self.response)

    def _to_llm_response(self, value: object) -> LLMResponse:
        if isinstance(value, LLMResponse):
            return value
        if isinstance(value, dict):
            return LLMResponse(
                ok=bool(value.get("ok")),
                content=value.get("content") if isinstance(value.get("content"), str) else (
                    None if value.get("content") is None else str(value.get("content"))
                ),
                model=value.get("model") if isinstance(value.get("model"), str) else None,
                error=value.get("error") if isinstance(value.get("error"), str) else None,
            )
        return LLMResponse(ok=True, content=str(value), model="fake")


class _FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeToolManager:
    def __init__(
        self,
        *,
        execute_result: ToolResult | None = None,
    ) -> None:
        self.execute_result = execute_result or ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"message": "ok"},
            text="ok",
            error=None,
        )
        self.get_tool_configs_calls: list[list[str]] = []
        self.execute_calls: list[AgentToolRequest] = []

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


class _FakeAgentSteering:
    def __init__(self, consume_results: list[bool] | None = None) -> None:
        self.consume_results = list(consume_results or [])

    def enqueue(self, run_id: str, item) -> None:  # noqa: ANN001
        return None

    def consume_abort_turn(self, run_id: str) -> bool:
        if self.consume_results:
            return self.consume_results.pop(0)
        return False

    def pop_steering_messages(self, run_id: str) -> list[str]:
        return []


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


def _entry(
    *,
    sequence: int,
    entry_type: AgentContextEntryType,
    payload: dict[str, object],
) -> AgentContextEntry:
    return AgentContextEntry(
        id=f"entry-{sequence}",
        run_id="run-1",
        context_id="thread-1",
        sequence=sequence,
        entry_type=entry_type,
        payload=payload,
        source_step_id="support_agent",
        idempotency_key=f"entry:{sequence}",
        created_at="2026-04-22T00:00:00Z",
    )


def _build_use_case(
    *,
    store: _FakeStore,
    context_store: _FakeAgentContextStore,
    llm: _FakeLLM,
    agent_steering: _FakeAgentSteering | None = None,
    tool_manager: _FakeToolManager | None = None,
    append_runtime_event_use_case: _FakeAppendRuntimeEventUseCase | None = None,
    event_output_sanitizer: AgentEventOutputSanitizer | None = None,
) -> ExecuteAgentStepUseCase:
    runner = build_agent_runner(
        agent_context_store=context_store,
        agent_steering=agent_steering,
        llm=llm,
        tool_manager=tool_manager,
        append_runtime_event_use_case=append_runtime_event_use_case,
        event_output_sanitizer=event_output_sanitizer,
    )
    return ExecuteAgentStepUseCase(store=store, runner=runner)


def test_execute_agent_step_appends_context_and_moves_to_next() -> None:
    store = _FakeStore()
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM()
    use_case = _build_use_case(
        store=store,
        context_store=context_store,
        llm=llm,
    )
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "context_id": "thread-1",
                "max_turns": 1,
                "next": "send_reply",
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "send_reply"
    assert result.execution is not None
    assert result.execution.output == AgentOutput(
        text="Hello back.",
        text_ref="data.final.text",
        data={
            "context_id": "thread-1",
            "final": {"text": "Hello back."},
            "turn_count": 1,
            "tool_call_count": 0,
            "stop_reason": "final",
        },
    )
    assert context.step_executions["support_agent"] == result.execution
    assert context_store.appended[0]["entry_type"] == AgentContextEntryType.USER_MESSAGE
    assert context_store.appended[0]["payload"] == {"type": "user_message", "text": "Hi"}
    assert context_store.appended[1]["entry_type"] == AgentContextEntryType.ASSISTANT_MESSAGE
    assert context_store.appended[1]["payload"] == {
        "type": "assistant_message",
        "turn_id": "turn-1",
        "message_type": "final",
        "text": "Hello back.",
    }
    assert len(llm.calls) == 1
    _assert_system_message_contains(llm.calls[0].messages[0], step_system="Be useful.")
    assert llm.calls[0].messages[1:] == (LLMMessage.user("Hi"),)
    assert llm.calls[0].tools == ()
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "send_reply",
            "context": context,
        }
    ]


def test_execute_agent_step_rebuilds_messages_from_existing_context() -> None:
    context_store = _FakeAgentContextStore(
        [
            _entry(
                sequence=1,
                entry_type=AgentContextEntryType.USER_MESSAGE,
                payload={"type": "user_message", "text": "Hello"},
            ),
            _entry(
                sequence=2,
                entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
                payload={"type": "assistant_message", "turn_id": "turn-1", "text": "Hi"},
            ),
        ]
    )
    llm = _FakeLLM(response={"ok": True, "content": "Second answer"})
    use_case = _build_use_case(
        store=_FakeStore(),
        context_store=context_store,
        llm=llm,
    )

    use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Again",
                "context_id": "thread-1",
            },
            context=RunContext(inputs={}, step_executions={}),
        )
    )

    _assert_system_message_contains(llm.calls[0].messages[0], step_system="Be useful.")
    assert llm.calls[0].messages[1:] == (
        LLMMessage.user("Hello"),
        LLMMessage.assistant("Hi"),
        LLMMessage.user("Again"),
    )
    assert context_store.appended[0]["idempotency_key"] == "user:support_agent:turn-2"
    assert context_store.appended[1]["idempotency_key"] == "assistant:support_agent:turn-2"


def test_execute_agent_step_supports_tool_call_then_success() -> None:
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
    use_case = _build_use_case(
        store=_FakeStore(),
        context_store=_FakeAgentContextStore(),
        llm=llm,
        tool_manager=tool_manager,
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "tools": ["notify"],
                "max_turns": 3,
            },
            context=RunContext(inputs={}, step_executions={}),
        )
    )

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.execution is not None
    assert result.execution.output == AgentOutput(
        text="Done.",
        text_ref="data.final.text",
        data={
            "context_id": "run-1",
            "final": {"text": "Done."},
            "turn_count": 2,
            "tool_call_count": 1,
            "stop_reason": "success",
        },
    )
    assert tool_manager.get_tool_configs_calls == [["notify"]]
    assert tool_manager.execute_calls == [
        AgentToolRequest(
            run_id="run-1",
            step_id="support_agent",
            context_id="run-1",
            turn_id="turn-1",
            tool_call_id="openai-call-1",
            tool="notify",
            args={"message": "hello"},
            allowed_tools=["notify"],
        )
    ]
    assert len(llm.calls) == 2
    _assert_system_message_contains(llm.calls[0].messages[0], step_system="Be useful.")
    assert llm.calls[0].messages[1:] == (LLMMessage.user("Hi"),)
    assert [tool.name for tool in llm.calls[0].tools] == ["notify"]
    _assert_system_message_contains(llm.calls[1].messages[0], step_system="Be useful.")
    assert llm.calls[1].messages[1:] == (
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
    assert [tool.name for tool in llm.calls[1].tools] == ["notify"]


def test_execute_agent_step_interrupts_and_advances_to_next_step() -> None:
    store = _FakeStore()
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        response=LLMResponse(
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
        )
    )
    use_case = _build_use_case(
        store=store,
        context_store=context_store,
        llm=llm,
        agent_steering=_FakeAgentSteering(consume_results=[True]),
        tool_manager=_FakeToolManager(),
    )
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "context_id": "thread-1",
                "max_turns": 2,
                "tools": ["notify"],
                "next": "send_reply",
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "send_reply"
    assert result.execution is not None
    assert result.execution.output == AgentOutput(
        text="Interrupted. Send another message if you want to continue.",
        text_ref="data.final.text",
        data={
            "context_id": "thread-1",
            "final": {"text": "Interrupted. Send another message if you want to continue."},
            "turn_count": 1,
            "tool_call_count": 0,
            "stop_reason": "interrupted",
        },
    )
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "send_reply",
            "context": context,
        }
    ]


def test_execute_agent_step_emits_agent_tool_events() -> None:
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
    use_case = _build_use_case(
        store=_FakeStore(),
        context_store=_FakeAgentContextStore(),
        llm=llm,
        tool_manager=tool_manager,
        append_runtime_event_use_case=append_event,
    )

    use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "tools": ["notify"],
                "max_turns": 3,
            },
            context=RunContext(inputs={}, step_executions={}),
        )
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


def test_execute_agent_step_advances_when_agent_reaches_max_turns() -> None:
    store = _FakeStore()
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
            )
        ]
    )
    use_case = _build_use_case(
        store=store,
        context_store=context_store,
        llm=llm,
        tool_manager=_FakeToolManager(),
    )
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "context_id": "thread-1",
                "max_turns": 1,
                "tools": ["notify"],
                "next": "send_reply",
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "send_reply"
    assert result.execution is not None
    assert result.execution.output == AgentOutput(
        text=(
            "I reached the turn limit before finishing. "
            "Send another message if you want me to continue."
        ),
        text_ref="data.final.text",
        data={
            "context_id": "thread-1",
            "final": {
                "text": (
                    "I reached the turn limit before finishing. "
                    "Send another message if you want me to continue."
                )
            },
            "turn_count": 1,
            "tool_call_count": 1,
            "stop_reason": "max_turns_exhausted",
        },
    )
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "send_reply",
            "context": context,
        }
    ]


def test_execute_agent_step_sanitizes_agent_tool_events() -> None:
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                model="fake",
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="shell",
                            arguments_json='{"command":"Authorization: Bearer abc"}',
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
            name="shell",
            status=ToolResultStatus.COMPLETED,
            data={"logs": ["line1", "line2", "line3"], "password": "raw-secret"},
            text="abcdefghijklmnopqrstuvwxyz",
            error=None,
        )
    )
    append_event = _FakeAppendRuntimeEventUseCase()
    sanitizer = AgentEventOutputSanitizer(
        AgentEventOutputPolicy(max_text_chars=10, max_json_chars=80, max_array_items=2)
    )
    use_case = _build_use_case(
        store=_FakeStore(),
        context_store=_FakeAgentContextStore(),
        llm=llm,
        tool_manager=tool_manager,
        append_runtime_event_use_case=append_event,
        event_output_sanitizer=sanitizer,
    )

    use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "tools": ["shell"],
                "max_turns": 3,
            },
            context=RunContext(inputs={}, step_executions={}),
        )
    )

    assert append_event.calls[0]["event_type"] == RuntimeEventType.AGENT_TOOL_CALL
    tool_call_payload = append_event.calls[0]["payload"]
    assert isinstance(tool_call_payload, dict)
    assert tool_call_payload["tool_call_id"] == "openai-call-1"
    assert tool_call_payload["args"]["command"].startswith("Authorizat")

    assert append_event.calls[1]["event_type"] == RuntimeEventType.AGENT_TOOL_RESULT
    tool_result_payload = append_event.calls[1]["payload"]
    assert isinstance(tool_result_payload, dict)
    assert tool_result_payload["tool_call_id"] == "openai-call-1"
    output = tool_result_payload["output"]
    assert isinstance(output, dict)
    assert output["text"] == "abcdefghij..."
    assert output["value"]["password"] == "***REDACTED***"
    assert output["value"]["logs"] == ["line1", "line2"]


def test_execute_agent_step_supports_tool_call_then_plain_text_final() -> None:
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
            LLMResponse(ok=True, content="Done.", model="fake"),
        ]
    )
    use_case = _build_use_case(
        store=_FakeStore(),
        context_store=_FakeAgentContextStore(),
        llm=llm,
        tool_manager=_FakeToolManager(),
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "tools": ["notify"],
                "max_turns": 3,
            },
            context=RunContext(inputs={}, step_executions={}),
        )
    )

    assert result.execution is not None
    assert result.execution.output.data["final"]["text"] == "Done."
    assert result.execution.output.data["stop_reason"] == "success"


def test_execute_agent_step_fails_when_llm_fails() -> None:
    use_case = _build_use_case(
        store=_FakeStore(),
        context_store=_FakeAgentContextStore(),
        llm=_FakeLLM(response={"ok": False, "error": "no model"}),
    )

    with pytest.raises(ValueError, match="no model"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="support_agent",
                step_type=StepType.AGENT,
                step={"system": "Be useful.", "task": "Hi"},
                context=RunContext(inputs={}, step_executions={}),
            )
        )


def test_execute_agent_step_rejects_malformed_tool_call() -> None:
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
                            name="",
                            arguments_json='{"message":"hello"}',
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            ),
            LLMResponse(ok=True, content="Done.", model="fake"),
        ]
    )
    use_case = _build_use_case(
        store=_FakeStore(),
        context_store=context_store,
        llm=llm,
        tool_manager=_FakeToolManager(),
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "tools": ["notify"],
                "max_turns": 2,
            },
            context=RunContext(inputs={}, step_executions={}),
        )
    )

    assert result.execution is not None
    assert result.execution.output.data["final"]["text"] == "Done."
    assert len(llm.calls) == 2
    feedback_entries = [
        item
        for item in context_store.appended
        if item["entry_type"] == AgentContextEntryType.USER_MESSAGE
        and "returned tool_call without tool" in str(item["payload"].get("text", ""))
    ]
    assert len(feedback_entries) == 1
