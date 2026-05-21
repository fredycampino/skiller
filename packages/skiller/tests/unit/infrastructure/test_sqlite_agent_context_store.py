import json
import sqlite3

import pytest

from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntryType,
    AgentToolCallPayload,
    AgentUserMessagePayload,
)
from skiller.domain.agent.agent_run_identity import AgentContext
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult
from skiller.infrastructure.db.sqlite_agent_context_store import SqliteAgentContextStore
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore

pytestmark = pytest.mark.unit


RUN_ID = "run-1"
SOURCE_STEP_ID = "support_agent"
CONTEXT_ID = "thread-1"
AGENT_CONTEXT = AgentContext(
    run_id=RUN_ID,
    agent_id=SOURCE_STEP_ID,
    context_id=CONTEXT_ID,
)


def test_sqlite_agent_context_store_appends_and_lists_entries(tmp_path) -> None:
    db_path = tmp_path / "agent-context.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = SqliteAgentContextStore(str(db_path))

    first = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Hi",
    )
    second = store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        message_type="final",
        text="Hello",
        usage=LLMUsage(
            prompt_tokens=123,
            completion_tokens=45,
            total_tokens=168,
            provider="minimax",
            model="MiniMax-M2.5",
        ),
    )

    entries = store.list_entries(context_id=CONTEXT_ID)
    with sqlite3.connect(db_path) as conn:
        raw_row = conn.execute(
            """
            SELECT message_type, total_tokens, usage_json
            FROM agent_context_entries
            WHERE id = ?
            """,
            (second.id,),
        ).fetchone()

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
        provider="minimax",
        model="MiniMax-M2.5",
    )
    assert raw_row[0] == "final"
    assert raw_row[1] == 168
    assert json.loads(raw_row[2]) == {
        "prompt_tokens": 123,
        "completion_tokens": 45,
        "total_tokens": 168,
        "provider": "minimax",
        "model": "MiniMax-M2.5",
    }
    assert store.get_usage(context_id=CONTEXT_ID) == LLMUsage(
        prompt_tokens=123,
        completion_tokens=45,
        total_tokens=168,
        provider="minimax",
        model="MiniMax-M2.5",
    )


def test_sqlite_agent_context_store_supports_multiple_tool_calls_in_same_turn(tmp_path) -> None:
    db_path = tmp_path / "agent-context-tools.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = SqliteAgentContextStore(str(db_path))

    first = store.append_tool_call(
        context=AGENT_CONTEXT,
        tool_call=AgentToolCall(
            turn_id="turn-1",
            parent_sequence=None,
            tool_call_id="call-1",
            tool="notify",
            args={"message": "hello"},
        ),
    )
    second = store.append_tool_call(
        context=AGENT_CONTEXT,
        tool_call=AgentToolCall(
            turn_id="turn-1",
            parent_sequence=None,
            tool_call_id="call-2",
            tool="notify",
            args={"message": "world"},
        ),
    )
    first_result = store.append_tool_result(
        context=AGENT_CONTEXT,
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
        context=AGENT_CONTEXT,
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

    entries = store.list_entries(context_id=CONTEXT_ID)

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
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = SqliteAgentContextStore(str(db_path))

    assert store.next_turn_id(context_id=CONTEXT_ID) == "turn-1"

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Hi",
    )
    assert store.next_turn_id(context_id=CONTEXT_ID) == "turn-1"

    store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        message_type="tool_calls",
        text="I will inspect this.",
    )
    assert store.next_turn_id(context_id=CONTEXT_ID) == "turn-2"

    store.append_tool_call(
        context=AGENT_CONTEXT,
        tool_call=AgentToolCall(
            turn_id="turn-1",
            parent_sequence=2,
            tool_call_id="call-1",
            tool="notify",
            args={"message": "hello"},
        ),
    )
    assert store.next_turn_id(context_id=CONTEXT_ID) == "turn-3"


def test_sqlite_agent_context_store_returns_context_stats(tmp_path) -> None:
    db_path = tmp_path / "agent-context-stats.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = SqliteAgentContextStore(str(db_path))

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Hi",
    )
    store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        message_type="tool_calls",
        text="I will call a tool.",
        usage=LLMUsage(prompt_tokens=100, completion_tokens=25, total_tokens=125),
    )
    store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        message_type="final",
        text="Done",
        usage=LLMUsage(prompt_tokens=None, completion_tokens=12, total_tokens=None),
    )
    store.append_tool_call(
        context=AGENT_CONTEXT,
        tool_call=AgentToolCall(
            turn_id="turn-1",
            parent_sequence=2,
            tool_call_id="call-1",
            tool="notify",
            args={},
        ),
    )
    store.append_tool_result(
        context=AGENT_CONTEXT,
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

    stats = store.get_stats(context_id=CONTEXT_ID)

    assert stats.entries.total == 5
    assert stats.entries.user_messages == 1
    assert stats.entries.assistant_messages == 2
    assert stats.entries.tool_calls == 1
    assert stats.entries.tool_results == 1
    assert stats.usage.entries == 1
    assert stats.usage.total_prompt_tokens == 0
    assert stats.usage.total_response_tokens == 12
    assert stats.usage.total_tokens == 0


def test_sqlite_agent_context_store_returns_last_final_usage(tmp_path) -> None:
    db_path = tmp_path / "agent-context-last-final-usage.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = SqliteAgentContextStore(str(db_path))

    store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        message_type="final",
        text="First final",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        message_type="tool_calls",
        text="Not final",
        usage=LLMUsage(prompt_tokens=20, completion_tokens=8, total_tokens=28),
    )
    latest = store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        message_type="final",
        text="Latest final",
        usage=LLMUsage(prompt_tokens=30, completion_tokens=9, total_tokens=39),
    )

    entries = store.list_entries(context_id=CONTEXT_ID)
    stats = store.get_stats(context_id=CONTEXT_ID)

    assert isinstance(latest.payload, AgentAssistantMessagePayload)
    assert latest.payload.total_tokens == 39
    assert store.get_usage(context_id=CONTEXT_ID) == LLMUsage(
        prompt_tokens=30,
        completion_tokens=9,
        total_tokens=39,
    )
    assert stats.usage.entries == 1
    assert stats.usage.total_prompt_tokens == 30
    assert stats.usage.total_response_tokens == 9
    assert stats.usage.total_tokens == 39
    assert [entry.usage.total_tokens for entry in entries if entry.usage is not None] == [
        15,
        28,
        39,
    ]


def test_sqlite_agent_context_store_lists_context_window_from_final_marker(tmp_path) -> None:
    db_path = tmp_path / "agent-context-window.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = SqliteAgentContextStore(str(db_path))

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Task",
    )
    old = store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        message_type="final",
        text="Old",
        usage=LLMUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
    )
    tool_calls = store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        message_type="tool_calls",
        text="",
        usage=LLMUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5),
    )
    store.append_tool_call(
        context=AGENT_CONTEXT,
        tool_call=AgentToolCall(
            turn_id="turn-2",
            parent_sequence=tool_calls.sequence,
            tool_call_id="call-1",
            tool="notify",
            args={},
        ),
    )
    store.append_tool_result(
        context=AGENT_CONTEXT,
        tool_result=AgentToolResult(
            turn_id="turn-2",
            parent_sequence=tool_calls.sequence,
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
    marker = store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        message_type="final",
        text="Marker",
        usage=LLMUsage(prompt_tokens=13, completion_tokens=2, total_tokens=15),
    )
    latest = store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-4",
        message_type="final",
        text="Latest",
        usage=LLMUsage(prompt_tokens=14, completion_tokens=6, total_tokens=20),
    )

    entries = store.list_context_window(context_id=CONTEXT_ID, window_tokens=10)

    assert isinstance(old.payload, AgentAssistantMessagePayload)
    assert old.payload.total_tokens == 10
    assert [entry.id for entry in entries] == [marker.id, latest.id]


def test_sqlite_agent_context_store_returns_full_context_when_window_is_not_exceeded(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-full.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = SqliteAgentContextStore(str(db_path))

    first = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Task",
    )
    final = store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        message_type="final",
        text="Done",
        usage=LLMUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
    )

    entries = store.list_context_window(context_id=CONTEXT_ID, window_tokens=10)

    assert [entry.id for entry in entries] == [first.id, final.id]


def test_sqlite_agent_context_store_returns_full_context_without_final_marker(tmp_path) -> None:
    db_path = tmp_path / "agent-context-window-no-marker.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = SqliteAgentContextStore(str(db_path))

    first = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Task",
    )
    tool_calls = store.append_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        message_type="tool_calls",
        text="",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    )

    entries = store.list_context_window(context_id=CONTEXT_ID, window_tokens=10)

    assert [entry.id for entry in entries] == [first.id, tool_calls.id]
