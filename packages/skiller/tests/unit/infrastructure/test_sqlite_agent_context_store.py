import json
import sqlite3
from dataclasses import dataclass

import pytest

from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntryType,
    AgentToolCallPayload,
    AgentUserMessagePayload,
)
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult
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
        text="Hi",
    )
    second = store.append_assistant_message(
        scope=scope,
        turn_id="turn-1",
        message_type="final",
        text="Hello",
        usage=LLMUsage(prompt_tokens=123, completion_tokens=45, total_tokens=168),
    )

    entries = store.list_entries(scope=scope)
    with sqlite3.connect(db_path) as conn:
        raw_usage = conn.execute(
            """
            SELECT usage_json
            FROM agent_context_entries
            WHERE id = ?
            """,
            (second.id,),
        ).fetchone()[0]

    assert [entry.id for entry in entries] == [first.id, second.id]
    assert [entry.sequence for entry in entries] == [1, 2]
    assert entries[0].payload == AgentUserMessagePayload(text="Hi")
    assert entries[1].entry_type == AgentContextEntryType.ASSISTANT_MESSAGE
    assert entries[1].payload == AgentAssistantMessagePayload(
        turn_id="turn-1",
        message_type="final",
        text="Hello",
        total_tokens=168,
    )
    assert entries[0].usage is None
    assert entries[1].usage == LLMUsage(
        prompt_tokens=123,
        completion_tokens=45,
        total_tokens=168,
    )
    assert json.loads(raw_usage) == {
        "prompt_tokens": 123,
        "completion_tokens": 45,
        "total_tokens": 168,
    }
    assert store.get_usage(scope=scope) == LLMUsage(
        prompt_tokens=123,
        completion_tokens=45,
        total_tokens=168,
    )


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
        tool_call=AgentToolCall(
            turn_id="turn-1",
            parent_sequence=None,
            tool_call_id="call-1",
            tool="notify",
            args={"message": "hello"},
        ),
    )
    second = store.append_tool_call(
        scope=scope,
        tool_call=AgentToolCall(
            turn_id="turn-1",
            parent_sequence=None,
            tool_call_id="call-2",
            tool="notify",
            args={"message": "world"},
        ),
    )
    first_result = store.append_tool_result(
        scope=scope,
        tool_result=AgentToolResult(
            turn_id="turn-1",
            parent_sequence=None,
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
    second_result = store.append_tool_result(
        scope=scope,
        tool_result=AgentToolResult(
            turn_id="turn-1",
            parent_sequence=None,
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

    assert [entry.id for entry in entries] == [
        first.id,
        second.id,
        first_result.id,
        second_result.id,
    ]
    assert entries[0].payload == AgentToolCallPayload(
        turn_id="turn-1",
        parent_sequence=None,
        tool_call_id="call-1",
        tool="notify",
        args={"message": "hello"},
    )
    assert entries[1].payload == AgentToolCallPayload(
        turn_id="turn-1",
        parent_sequence=None,
        tool_call_id="call-2",
        tool="notify",
        args={"message": "world"},
    )
    assert entries[2].payload.tool_call_id == "call-2"


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
        tool_call=AgentToolCall(
            turn_id="turn-1",
            parent_sequence=2,
            tool_call_id="call-1",
            tool="notify",
            args={"message": "hello"},
        ),
    )
    assert store.next_turn_id(scope=scope) == "turn-3"


def test_sqlite_agent_context_store_returns_context_stats(tmp_path) -> None:
    db_path = tmp_path / "agent-context-stats.db"
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

    store.append_user_message(scope=scope, text="Hi")
    store.append_assistant_message(
        scope=scope,
        turn_id="turn-1",
        message_type="tool_calls",
        text="I will call a tool.",
        usage=LLMUsage(prompt_tokens=100, completion_tokens=25, total_tokens=125),
    )
    store.append_assistant_message(
        scope=scope,
        turn_id="turn-2",
        message_type="final",
        text="Done",
        usage=LLMUsage(prompt_tokens=None, completion_tokens=12, total_tokens=None),
    )
    store.append_tool_call(
        scope=scope,
        tool_call=AgentToolCall(
            turn_id="turn-1",
            parent_sequence=2,
            tool_call_id="call-1",
            tool="notify",
            args={},
        ),
    )
    store.append_tool_result(
        scope=scope,
        tool_result=AgentToolResult(
            turn_id="turn-1",
            parent_sequence=2,
            tool_call_id="call-1",
            result=ToolResult(
                name="notify",
                status=ToolResultStatus.COMPLETED,
                data={},
                text="ok",
                error=None,
            ),
        ),
    )

    stats = store.get_stats(scope=scope)

    assert stats.entries.total == 5
    assert stats.entries.user_messages == 1
    assert stats.entries.assistant_messages == 2
    assert stats.entries.tool_calls == 1
    assert stats.entries.tool_results == 1
    assert stats.usage.entries == 2
    assert stats.usage.total_prompt_tokens == 100
    assert stats.usage.total_response_tokens == 37
    assert stats.usage.total_tokens == 125
