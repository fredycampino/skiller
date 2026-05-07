import pytest

from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.application.agent.tools.tool_turn_executor_model import (
    AgentTurnLoop,
    ToolTurnRequest,
    ToolTurnStatus,
)
from skiller.application.ports.llm.llm_port import (
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
)
from skiller.domain.agent.agent_context_model import AgentContextEntry, AgentContextEntryType
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus
from tests.helpers.agent_runner import build_agent_tool_turn_executor

pytestmark = pytest.mark.unit


class _FakeAgentContextStore:
    def __init__(self) -> None:
        self.entries: list[AgentContextEntry] = []

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
        entry = AgentContextEntry(
            id=f"entry-{len(self.entries) + 1}",
            run_id=run_id,
            context_id=context_id,
            sequence=len(self.entries) + 1,
            entry_type=entry_type,
            payload=payload,
            source_step_id=source_step_id,
            idempotency_key=idempotency_key,
            created_at="2026-05-05T00:00:00Z",
        )
        self.entries.append(entry)
        return entry


class _FakeToolManager:
    def __init__(self) -> None:
        self.execute_calls: list[AgentToolRequest] = []

    def execute(self, request: AgentToolRequest) -> ToolResult:
        self.execute_calls.append(request)
        return ToolResult(
            name=request.tool,
            status=ToolResultStatus.COMPLETED,
            data=request.args,
            text=str(request.args.get("message", "")),
            error=None,
        )


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


def test_tool_turn_executor_returns_one_result_per_tool_call() -> None:
    context_store = _FakeAgentContextStore()
    tool_manager = _FakeToolManager()
    executor = build_agent_tool_turn_executor(
        agent_context_store=context_store,
        agent_steering=_FakeAgentSteering(),
        tool_manager=tool_manager,
    )
    turn_loop = AgentTurnLoop(max_turns=3)

    results = executor.execute(
        ToolTurnRequest(
            run_id="run-1",
            step_id="support_agent",
            context_id="thread-1",
            turn_id="turn-1",
            response=LLMResponse(
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
                            arguments_json='{"message":"world"',
                        ),
                    ),
                    LLMToolCall(
                        id="call-3",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"done"}',
                        ),
                    ),
                ),
            ),
            allowed_tools=["notify"],
            max_tool_calls=5,
            turn_loop=turn_loop,
        )
    )

    assert [
        (result.tool_call_id, result.tool, result.status) for result in results.items
    ] == [
        ("call-1", "notify", ToolTurnStatus.EXECUTED),
        ("call-2", "notify", ToolTurnStatus.INVALID),
        ("call-3", "notify", ToolTurnStatus.EXECUTED),
    ]
    assert results.executed_count() == 2
    assert results.is_interrupted() is False
    assert [request.tool_call_id for request in tool_manager.execute_calls] == [
        "call-1",
        "call-3",
    ]
    assert turn_loop.turn_count == 1
    assert [entry.entry_type for entry in context_store.entries] == [
        AgentContextEntryType.TOOL_CALL,
        AgentContextEntryType.TOOL_RESULT,
        AgentContextEntryType.USER_MESSAGE,
        AgentContextEntryType.TOOL_CALL,
        AgentContextEntryType.TOOL_RESULT,
    ]
    assert context_store.entries[0].payload["parent_sequence"] is None


def test_tool_turn_executor_returns_empty_list_without_tool_calls() -> None:
    executor = build_agent_tool_turn_executor(
        agent_context_store=_FakeAgentContextStore(),
        agent_steering=_FakeAgentSteering(),
        tool_manager=_FakeToolManager(),
    )
    turn_loop = AgentTurnLoop(max_turns=3)

    results = executor.execute(
        ToolTurnRequest(
            run_id="run-1",
            step_id="support_agent",
            context_id="thread-1",
            turn_id="turn-1",
            response=LLMResponse(ok=True, content="Done."),
            allowed_tools=["notify"],
            max_tool_calls=5,
            turn_loop=turn_loop,
        )
    )

    assert results.items == []
    assert results.executed_count() == 0
    assert results.is_interrupted() is False
    assert turn_loop.turn_count == 0


def test_tool_turn_executor_interrupts_before_next_tool_call() -> None:
    context_store = _FakeAgentContextStore()
    tool_manager = _FakeToolManager()
    executor = build_agent_tool_turn_executor(
        agent_context_store=context_store,
        agent_steering=_FakeAgentSteering(consume_results=[False, True]),
        tool_manager=tool_manager,
    )
    turn_loop = AgentTurnLoop(max_turns=3)

    results = executor.execute(
        ToolTurnRequest(
            run_id="run-1",
            step_id="support_agent",
            context_id="thread-1",
            turn_id="turn-1",
            response=LLMResponse(
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
            ),
            allowed_tools=["notify"],
            max_tool_calls=5,
            turn_loop=turn_loop,
        )
    )

    assert [
        (result.tool_call_id, result.tool, result.status) for result in results.items
    ] == [
        ("call-1", "notify", ToolTurnStatus.EXECUTED),
        ("turn-1", "agent", ToolTurnStatus.INTERRUPTED),
    ]
    assert results.executed_count() == 1
    assert results.is_interrupted() is True
    assert [request.tool_call_id for request in tool_manager.execute_calls] == ["call-1"]
    assert turn_loop.turn_count == 1
    assert [entry.entry_type for entry in context_store.entries] == [
        AgentContextEntryType.TOOL_CALL,
        AgentContextEntryType.TOOL_RESULT,
        AgentContextEntryType.USER_MESSAGE,
    ]
    assert context_store.entries[-1].payload == {
        "type": "user_message",
        "text": "User interrupted the current agent turn.",
    }


def test_tool_turn_executor_rejects_tool_call_batch_over_limit() -> None:
    context_store = _FakeAgentContextStore()
    executor = build_agent_tool_turn_executor(
        agent_context_store=context_store,
        agent_steering=_FakeAgentSteering(),
        tool_manager=_FakeToolManager(),
    )
    turn_loop = AgentTurnLoop(max_turns=3)

    results = executor.execute(
        ToolTurnRequest(
            run_id="run-1",
            step_id="support_agent",
            context_id="thread-1",
            turn_id="turn-1",
            response=LLMResponse(
                ok=True,
                tool_calls=(
                    LLMToolCall(
                        id="call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"one"}',
                        ),
                    ),
                    LLMToolCall(
                        id="call-2",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"two"}',
                        ),
                    ),
                ),
            ),
            allowed_tools=["notify"],
            max_tool_calls=1,
            turn_loop=turn_loop,
        )
    )

    assert [
        (result.tool_call_id, result.tool, result.status) for result in results.items
    ] == [("turn-1", "agent", ToolTurnStatus.INVALID)]
    assert results.executed_count() == 0
    assert results.is_interrupted() is False
    assert turn_loop.turn_count == 1
    assert [entry.entry_type for entry in context_store.entries] == [
        AgentContextEntryType.USER_MESSAGE,
    ]
    assert context_store.entries[0].payload == {
        "type": "user_message",
        "text": (
            "Too many tool calls in step 'support_agent': received 2, maximum allowed is 1. "
            "Return at most 1 tool call(s) in one response."
        ),
    }


def test_tool_turn_executor_links_tool_entries_to_assistant_message() -> None:
    context_store = _FakeAgentContextStore()
    executor = build_agent_tool_turn_executor(
        agent_context_store=context_store,
        agent_steering=_FakeAgentSteering(),
        tool_manager=_FakeToolManager(),
    )
    turn_loop = AgentTurnLoop(max_turns=3)

    executor.execute(
        ToolTurnRequest(
            run_id="run-1",
            step_id="support_agent",
            context_id="thread-1",
            turn_id="turn-1",
            response=LLMResponse(
                ok=True,
                content="I will inspect the repo first.",
                tool_calls=(
                    LLMToolCall(
                        id="call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"hello"}',
                        ),
                    ),
                ),
            ),
            allowed_tools=["notify"],
            max_tool_calls=5,
            turn_loop=turn_loop,
        )
    )

    assert [entry.entry_type for entry in context_store.entries] == [
        AgentContextEntryType.ASSISTANT_MESSAGE,
        AgentContextEntryType.TOOL_CALL,
        AgentContextEntryType.TOOL_RESULT,
    ]
    assert context_store.entries[0].payload["message_type"] == "tool_calls"
    assert context_store.entries[1].payload["parent_sequence"] == context_store.entries[0].sequence
    assert context_store.entries[2].payload["parent_sequence"] == context_store.entries[0].sequence
