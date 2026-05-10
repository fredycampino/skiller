from dataclasses import dataclass

import pytest
from skiller.domain.agent.agent_context_model import (
    AgentContextEntryType,
    AgentContextToolCall,
    AgentContextToolResult,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus
from skiller.infrastructure.db.sqlite_agent_context_store import SqliteAgentContextStore
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _AgentScope:
    run_id: str = "run-1"
    agent_id: str = "support_agent"
    context_id: str = "thread-1"


def test_sqlite_agent_context_store_appends_and_lists_entries(tmp_path) -> None:
    db_path = tmp_path / "agent-context.db"
    run_store = SqliteStateStore(str(db_path))
    run_store.init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id="run-1",
    )
    store = SqliteAgentContextStore(str(db_path))
    scope = _AgentScope()

    first = store.append_user_message(
        scope=scope,
        turn_id="turn-1",
        text="Hi",
    )
    second = store.append_assistant_message(
        scope=scope,
        turn_id="turn-1",
        message_type="final",
        text="Hello",
    )

    entries = store.list_entries(scope=scope)

    assert [entry.id for entry in entries] == [first.id, second.id]
    assert [entry.sequence for entry in entries] == [1, 2]
    assert entries[0].payload == {"type": "user_message", "text": "Hi"}
    assert entries[1].entry_type == AgentContextEntryType.ASSISTANT_MESSAGE
    assert entries[1].payload["message_type"] == "final"


def test_sqlite_agent_context_store_uses_idempotency_key(tmp_path) -> None:
    db_path = tmp_path / "agent-context-idempotency.db"
    run_store = SqliteStateStore(str(db_path))
    run_store.init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id="run-1",
    )
    store = SqliteAgentContextStore(str(db_path))
    scope = _AgentScope()

    first = store.append_user_message(
        scope=scope,
        turn_id="turn-1",
        text="Hi",
    )
    duplicate = store.append_user_message(
        scope=scope,
        turn_id="turn-1",
        text="Ignored",
    )

    entries = store.list_entries(scope=scope)

    assert duplicate == first
    assert len(entries) == 1
    assert entries[0].payload == {"type": "user_message", "text": "Hi"}


def test_sqlite_agent_context_store_supports_multiple_tool_calls_in_same_turn(tmp_path) -> None:
    db_path = tmp_path / "agent-context-tools.db"
    run_store = SqliteStateStore(str(db_path))
    run_store.init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id="run-1",
    )
    store = SqliteAgentContextStore(str(db_path))
    scope = _AgentScope()

    first = store.append_tool_call(
        scope=scope,
        turn_id="turn-1",
        parent_sequence=None,
        tool_call=AgentContextToolCall(
            id="call-1",
            tool="notify",
            args={"message": "hello"},
        ),
    )
    second = store.append_tool_call(
        scope=scope,
        turn_id="turn-1",
        parent_sequence=None,
        tool_call=AgentContextToolCall(
            id="call-2",
            tool="notify",
            args={"message": "world"},
        ),
    )
    duplicate = store.append_tool_result(
        scope=scope,
        turn_id="turn-1",
        parent_sequence=None,
        tool_result=AgentContextToolResult(
            tool_call_id="call-2",
            result=ToolResult(
                name="notify",
                status=ToolResultStatus.COMPLETED,
                data={"message": "world"},
                text="world",
                error=None,
            ),
        ),
    )
    duplicate_again = store.append_tool_result(
        scope=scope,
        turn_id="turn-1",
        parent_sequence=None,
        tool_result=AgentContextToolResult(
            tool_call_id="call-2",
            result=ToolResult(
                name="notify",
                status=ToolResultStatus.COMPLETED,
                data={"message": "ignored"},
                text="ignored",
                error=None,
            ),
        ),
    )

    entries = store.list_entries(scope=scope)

    assert [entry.id for entry in entries] == [first.id, second.id, duplicate.id]
    assert duplicate_again == duplicate
    assert entries[0].payload["tool_call_id"] == "call-1"
    assert entries[1].payload["tool_call_id"] == "call-2"
    assert entries[2].payload["tool_call_id"] == "call-2"


def test_sqlite_agent_context_store_returns_next_turn_id(tmp_path) -> None:
    db_path = tmp_path / "agent-context-next-turn.db"
    run_store = SqliteStateStore(str(db_path))
    run_store.init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id="run-1",
    )
    store = SqliteAgentContextStore(str(db_path))
    scope = _AgentScope()

    assert store.next_turn_id(scope=scope) == "turn-1"

    store.append_user_message(
        scope=scope,
        turn_id="turn-1",
        text="Hi",
    )
    assert store.next_turn_id(scope=scope) == "turn-1"

    store.append_assistant_message(
        scope=scope,
        turn_id="turn-1",
        message_type="tool_calls",
        text="I will inspect this.",
    )
    assert store.next_turn_id(scope=scope) == "turn-2"

    store.append_tool_call(
        scope=scope,
        turn_id="turn-1",
        parent_sequence=2,
        tool_call=AgentContextToolCall(
            id="call-1",
            tool="notify",
            args={"message": "hello"},
        ),
    )
    assert store.next_turn_id(scope=scope) == "turn-3"
