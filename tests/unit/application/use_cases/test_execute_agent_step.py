import pytest

from skiller.application.use_cases.agent.execute_agent_step import ExecuteAgentStepUseCase
from skiller.application.use_cases.agent.tool_manager_model import AgentToolRequest
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.application.use_cases.shared.step_execution_result import StepExecutionStatus
from skiller.domain.agent.agent_context_model import AgentContextEntry, AgentContextEntryType
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.step_execution_model import AgentOutput
from skiller.domain.step.step_type import StepType
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus

pytestmark = pytest.mark.unit


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

    def append_entry(
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
        response: dict[str, object] | None = None,
        responses: list[dict[str, object]] | None = None,
    ) -> None:
        self.response = response or {"ok": True, "content": "Hello back.", "model": "fake"}
        self.responses = list(responses or [])
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        messages: list[dict[str, str]],
        config: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append({"messages": messages, "config": config})
        if self.responses:
            return self.responses.pop(0)
        return self.response


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
        self.get_tools_calls: list[list[str]] = []
        self.execute_calls: list[AgentToolRequest] = []

    def get_tools(self, allowed_tools: list[str]) -> list[_FakeTool]:
        self.get_tools_calls.append(list(allowed_tools))
        return [_FakeTool(name=tool) for tool in allowed_tools]

    def execute(self, request: AgentToolRequest) -> ToolResult:
        self.execute_calls.append(request)
        return self.execute_result


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


def test_execute_agent_step_appends_context_and_moves_to_next() -> None:
    store = _FakeStore()
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM()
    use_case = ExecuteAgentStepUseCase(
        store=store,
        agent_context_store=context_store,
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
        "text": "Hello back.",
    }
    assert llm.calls == [
        {
            "messages": [
                {"role": "system", "content": "Be useful."},
                {"role": "user", "content": "Hi"},
            ],
            "config": {"step_id": "support_agent", "agent": True, "max_turns": 1},
        }
    ]
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
    llm = _FakeLLM(response={"ok": True, "content": '{"reply":"Second answer"}'})
    use_case = ExecuteAgentStepUseCase(
        store=_FakeStore(),
        agent_context_store=context_store,
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

    assert llm.calls[0]["messages"] == [
        {"role": "system", "content": "Be useful."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "Again"},
    ]
    assert context_store.appended[0]["idempotency_key"] == "user:support_agent:turn-2"
    assert context_store.appended[1]["idempotency_key"] == "final:support_agent:turn-2"


def test_execute_agent_step_supports_tool_call_then_success() -> None:
    llm = _FakeLLM(
        responses=[
            {
                "ok": True,
                "content": '{"type":"tool_call","tool":"notify","args":{"message":"hello"}}',
                "model": "fake",
            },
            {
                "ok": True,
                "content": '{"type":"success","text":"Done."}',
                "model": "fake",
            },
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
    use_case = ExecuteAgentStepUseCase(
        store=_FakeStore(),
        agent_context_store=_FakeAgentContextStore(),
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
    assert tool_manager.get_tools_calls == [["notify"]]
    assert tool_manager.execute_calls == [
        AgentToolRequest(
            run_id="run-1",
            step_id="support_agent",
            context_id="run-1",
            turn_id="turn-1",
            tool="notify",
            args={"message": "hello"},
            allowed_tools=["notify"],
        )
    ]
    assert len(llm.calls) == 2
    assert llm.calls[0]["config"] == {
        "step_id": "support_agent",
        "agent": True,
        "max_turns": 3,
        "tools": ["notify"],
    }
    assert llm.calls[0]["messages"][0]["role"] == "system"
    assert "Be useful." in llm.calls[0]["messages"][0]["content"]
    assert "If you need to use a tool" in llm.calls[0]["messages"][0]["content"]
    assert (
        'Use only tool names from this list: ["notify"]'
        in llm.calls[0]["messages"][0]["content"]
    )
    assert (
        "When the task is complete, answer the user directly in plain text."
        in llm.calls[0]["messages"][0]["content"]
    )
    assert (
        "Do not wrap the final answer in JSON unless you are making a tool call."
        in llm.calls[0]["messages"][0]["content"]
    )
    assert "Do not emit an error terminal response." in llm.calls[0]["messages"][0]["content"]
    assert llm.calls[0]["messages"][1:] == [
        {"role": "user", "content": "Hi"},
    ]
    assert llm.calls[1]["config"] == {
        "step_id": "support_agent",
        "agent": True,
        "max_turns": 3,
        "tools": ["notify"],
    }
    assert llm.calls[1]["messages"][0]["role"] == "system"
    assert "Be useful." in llm.calls[1]["messages"][0]["content"]
    assert llm.calls[1]["messages"][1:] == [
        {"role": "user", "content": "Hi"},
        {
            "role": "assistant",
            "content": (
                '{"args": {"message": "hello"}, "tool": "notify", '
                '"turn_id": "turn-1", "type": "tool_call"}'
            ),
        },
        {
            "role": "user",
            "content": (
                '{"data": {"message": "sent"}, "error": null, '
                '"status": "COMPLETED", "text": "sent", "tool": "notify", '
                '"turn_id": "turn-1", "type": "tool_result"}'
            ),
        },
    ]


def test_execute_agent_step_supports_tool_call_then_plain_text_final() -> None:
    llm = _FakeLLM(
        responses=[
            {
                "ok": True,
                "content": '{"type":"tool_call","tool":"notify","args":{"message":"hello"}}',
                "model": "fake",
            },
            {
                "ok": True,
                "content": "Done.",
                "model": "fake",
            },
        ]
    )
    use_case = ExecuteAgentStepUseCase(
        store=_FakeStore(),
        agent_context_store=_FakeAgentContextStore(),
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


def test_execute_agent_step_accepts_markdown_fenced_tool_decisions() -> None:
    llm = _FakeLLM(
        responses=[
            {
                "ok": True,
                "content": (
                    "```json\n"
                    '{"type":"tool_call","tool":"notify","args":{"message":"hello"}}\n'
                    "```"
                ),
                "model": "fake",
            },
            {
                "ok": True,
                "content": "```json\n{\"type\":\"success\",\"text\":\"Done.\"}\n```",
                "model": "fake",
            },
        ]
    )
    tool_manager = _FakeToolManager()
    use_case = ExecuteAgentStepUseCase(
        store=_FakeStore(),
        agent_context_store=_FakeAgentContextStore(),
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

    assert result.execution is not None
    assert result.execution.output.data["final"]["text"] == "Done."
    assert tool_manager.execute_calls[0].args == {"message": "hello"}


def test_execute_agent_step_accepts_triple_quoted_json_blocks() -> None:
    llm = _FakeLLM(
        responses=[
            {
                "ok": True,
                "content": (
                    "'''json\n"
                    '{"type":"tool_call","tool":"notify","args":{"message":"hello"}}\n'
                    "'''"
                ),
                "model": "fake",
            },
            {
                "ok": True,
                "content": '"""json\n{"type":"success","text":"Done."}\n"""',
                "model": "fake",
            },
        ]
    )
    tool_manager = _FakeToolManager()
    use_case = ExecuteAgentStepUseCase(
        store=_FakeStore(),
        agent_context_store=_FakeAgentContextStore(),
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

    assert result.execution is not None
    assert result.execution.output.data["final"]["text"] == "Done."
    assert tool_manager.execute_calls[0].args == {"message": "hello"}


def test_execute_agent_step_fails_when_llm_fails() -> None:
    use_case = ExecuteAgentStepUseCase(
        store=_FakeStore(),
        agent_context_store=_FakeAgentContextStore(),
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
    llm = _FakeLLM(
        responses=[
            {
                "ok": True,
                "content": '{"type":"tool_call","args":{"message":"hello"}}',
                "model": "fake",
            }
        ]
    )
    use_case = ExecuteAgentStepUseCase(
        store=_FakeStore(),
        agent_context_store=_FakeAgentContextStore(),
        llm=llm,
        tool_manager=_FakeToolManager(),
    )

    with pytest.raises(ValueError, match="tool_call without tool"):
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
                    "max_turns": 1,
                },
                context=RunContext(inputs={}, step_executions={}),
            )
        )


def test_execute_agent_step_includes_raw_response_excerpt_when_decision_is_invalid() -> None:
    llm = _FakeLLM(
        responses=[
            {
                "ok": True,
                "content": '{"type":"tool_call","args":{"message":"hello"}}',
                "model": "fake",
            }
        ]
    )
    use_case = ExecuteAgentStepUseCase(
        store=_FakeStore(),
        agent_context_store=_FakeAgentContextStore(),
        llm=llm,
        tool_manager=_FakeToolManager(),
    )

    with pytest.raises(ValueError) as exc_info:
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
                    "max_turns": 1,
                },
                context=RunContext(inputs={}, step_executions={}),
            )
        )

    message = str(exc_info.value)
    assert "tool_call without tool" in message
    assert "Raw response:" in message
    assert '{"type":"tool_call","args":{"message":"hello"}}' in message
