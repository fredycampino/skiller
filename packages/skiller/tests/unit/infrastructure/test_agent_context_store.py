import json
import sqlite3

import pytest

from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntryType,
    AgentToolCallPayload,
    AgentUserMessagePayload,
)
from skiller.domain.agent.agent_llm_provider_model import AgentMiniMaxLLMModel
from skiller.domain.agent.agent_run_identity import AgentContext
from skiller.domain.agent.llm_model import LLMUsage
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult
from skiller.infrastructure.agent.agent_context_store import AgentContextStore
from skiller.infrastructure.db.sqlite_agent_context_datasource import (
    SqliteAgentContextDatasource,
)
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


def _store(db_path) -> AgentContextStore:
    return AgentContextStore(SqliteAgentContextDatasource(str(db_path)))


def test_agent_context_store_appends_and_lists_entries(tmp_path) -> None:
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
    store = _store(db_path)

    first = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Hi",
    )
    second = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Hello",
        usage=LLMUsage(
            prompt_tokens=123,
            completion_tokens=45,
            total_tokens=168,
            provider="minimax",
            model=AgentMiniMaxLLMModel.M2_5,
        ),
        window_tokens=168,
        window_start_sequence=1,
    )

    entries = store.list_entries(context_id=CONTEXT_ID)
    with sqlite3.connect(db_path) as conn:
        raw_row = conn.execute(
            """
            SELECT
              message_type,
              position_tokens,
              window_tokens,
              window_start_sequence,
              usage_json
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
    )
    assert entries[0].usage is None
    assert entries[1].usage == LLMUsage(
        prompt_tokens=123,
        completion_tokens=45,
        total_tokens=168,
        provider="minimax",
        model=AgentMiniMaxLLMModel.M2_5,
    )
    assert raw_row[0] == "final"
    assert raw_row[1] == 168
    assert raw_row[2] == 168
    assert raw_row[3] == 1
    assert json.loads(raw_row[4]) == {
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
        model=AgentMiniMaxLLMModel.M2_5,
    )


def test_agent_context_store_offsets_position_tokens_when_window_start_changes(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-position-token-reset.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = _store(db_path)

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Task",
    )
    first = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="First",
        usage=LLMUsage(prompt_tokens=90, completion_tokens=5, total_tokens=95),
        window_tokens=95,
        window_start_sequence=1,
    )
    reset_start = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Smaller window task",
    )
    reset = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Reset",
        usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        window_tokens=2,
        window_start_sequence=reset_start.sequence,
    )

    entries = store.list_entries(context_id=CONTEXT_ID)

    assert first.window_tokens == 95
    assert first.position_tokens == 95
    assert reset.window_tokens == 2
    assert reset.position_tokens == 97
    assert reset.window_start_sequence == reset_start.sequence
    assert reset.usage == LLMUsage(
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
    )
    position_tokens = [
        entry.position_tokens for entry in entries if entry.position_tokens
    ]
    assert position_tokens == [
        95,
        97,
    ]


def test_agent_context_store_recomputes_position_tokens_from_window_base(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-position-token-delta.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = _store(db_path)

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Task",
    )
    first = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="First",
        usage=LLMUsage(prompt_tokens=90, completion_tokens=5, total_tokens=95),
        window_tokens=95,
        window_start_sequence=1,
    )
    next_final = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Next",
        usage=LLMUsage(prompt_tokens=100, completion_tokens=5, total_tokens=105),
        window_tokens=105,
        window_start_sequence=1,
    )

    assert first.position_tokens == 95
    assert next_final.position_tokens == 105


def test_agent_context_store_does_not_duplicate_final_used_as_window_start(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-final-start.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = _store(db_path)

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Initial task",
    )
    base = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Base final",
        usage=LLMUsage(prompt_tokens=35, completion_tokens=5, total_tokens=40),
        window_tokens=40,
        window_start_sequence=1,
    )
    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current window task",
    )
    previous = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Previous current final",
        usage=LLMUsage(prompt_tokens=25, completion_tokens=5, total_tokens=30),
        window_tokens=30,
        window_start_sequence=3,
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Latest current final",
        usage=LLMUsage(prompt_tokens=45, completion_tokens=5, total_tokens=50),
        window_tokens=50,
        window_start_sequence=previous.sequence,
    )

    window = store.list_context_window(context_id=CONTEXT_ID, window_tokens=10)
    stats = store.get_stats(context_id=CONTEXT_ID)

    assert base.position_tokens == 40
    assert previous.position_tokens == 70
    assert latest.position_tokens == 90
    assert latest.window_start_sequence == previous.sequence
    assert [entry.id for entry in window.entries] == [latest.id]
    assert stats.entries == 5
    assert stats.estimated_tokens == 90
    assert stats.window.start_sequence == previous.sequence
    assert stats.window.end_sequence == 5
    assert stats.window.current_tokens == 50


def test_agent_context_store_supports_multiple_tool_calls_in_same_turn(tmp_path) -> None:
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
    store = _store(db_path)

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


def test_agent_context_store_returns_next_turn_id(tmp_path) -> None:
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
    store = _store(db_path)

    assert store.next_turn_id(context_id=CONTEXT_ID) == "turn-1"

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Hi",
    )
    assert store.next_turn_id(context_id=CONTEXT_ID) == "turn-1"

    store.append_tool_calls_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
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


def test_agent_context_store_returns_context_stats(tmp_path) -> None:
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
    store = _store(db_path)

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Hi",
    )
    store.append_tool_calls_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="I will call a tool.",
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Done",
        usage=LLMUsage(prompt_tokens=None, completion_tokens=12, total_tokens=None),
        window_tokens=0,
        window_start_sequence=1,
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

    assert stats.entries == 5
    assert stats.estimated_tokens == 0
    assert stats.window.start_sequence == 1
    assert stats.window.end_sequence == 5
    assert stats.window.current_tokens == 0


def test_agent_context_store_returns_last_final_usage(tmp_path) -> None:
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
    store = _store(db_path)

    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="First final",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        window_tokens=15,
        window_start_sequence=1,
    )
    store.append_tool_calls_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Not final",
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Latest final",
        usage=LLMUsage(prompt_tokens=30, completion_tokens=9, total_tokens=39),
        window_tokens=39,
        window_start_sequence=1,
    )

    entries = store.list_entries(context_id=CONTEXT_ID)
    stats = store.get_stats(context_id=CONTEXT_ID)

    assert isinstance(latest.payload, AgentAssistantMessagePayload)
    assert latest.window_tokens == 39
    assert latest.window_start_sequence == 1
    assert store.get_usage(context_id=CONTEXT_ID) == LLMUsage(
        prompt_tokens=30,
        completion_tokens=9,
        total_tokens=39,
    )
    assert stats.entries == 3
    assert stats.estimated_tokens == 39
    assert stats.window.start_sequence == 1
    assert stats.window.end_sequence == 3
    assert stats.window.current_tokens == 39
    assert [entry.usage.total_tokens for entry in entries if entry.usage is not None] == [
        15,
        39,
    ]


def test_agent_context_store_lists_context_window_from_final_marker(tmp_path) -> None:
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
    store = _store(db_path)

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Task",
    )
    old = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Old",
        usage=LLMUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        window_tokens=10,
        window_start_sequence=1,
    )
    tool_calls = store.append_tool_calls_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="",
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
    marker = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Marker",
        usage=LLMUsage(prompt_tokens=13, completion_tokens=2, total_tokens=15),
        window_tokens=15,
        window_start_sequence=1,
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-4",
        text="Latest",
        usage=LLMUsage(prompt_tokens=14, completion_tokens=6, total_tokens=20),
        window_tokens=20,
        window_start_sequence=1,
    )

    window = store.list_context_window(context_id=CONTEXT_ID, window_tokens=10)

    assert isinstance(old.payload, AgentAssistantMessagePayload)
    assert old.window_tokens == 10
    assert [entry.id for entry in window.entries] == [marker.id, latest.id]


def test_agent_context_store_returns_full_context_when_window_is_not_exceeded(
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
    store = _store(db_path)

    first = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Task",
    )
    final = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Done",
        usage=LLMUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        window_tokens=10,
        window_start_sequence=1,
    )

    window = store.list_context_window(context_id=CONTEXT_ID, window_tokens=10)

    assert [entry.id for entry in window.entries] == [first.id, final.id]


def test_agent_context_store_expands_window_when_limit_allows_older_entries(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-persisted.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = _store(db_path)

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Old task",
    )
    old_final = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Old final",
        usage=LLMUsage(prompt_tokens=60, completion_tokens=20, total_tokens=80),
        window_tokens=80,
        window_start_sequence=1,
    )
    marker = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Window task",
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Latest final",
        usage=LLMUsage(prompt_tokens=50, completion_tokens=10, total_tokens=60),
        window_tokens=60,
        window_start_sequence=marker.sequence,
    )

    window = store.list_context_window(context_id=CONTEXT_ID, window_tokens=100)

    assert latest.position_tokens == 140
    assert latest.window_tokens == 60
    assert latest.window_start_sequence == marker.sequence
    assert [entry.id for entry in window.entries] == [
        old_final.id,
        marker.id,
        latest.id,
    ]


def test_agent_context_store_moves_window_using_current_start_markers_only(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-current-start.db"
    run_store = SqliteStateStore(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = _store(db_path)

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Old task",
    )
    previous_window_final = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Previous window final",
        usage=LLMUsage(prompt_tokens=90, completion_tokens=10, total_tokens=100),
        window_tokens=100,
        window_start_sequence=1,
    )
    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current window task",
    )
    first_current_final = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="First current final",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=2, total_tokens=12),
        window_tokens=12,
        window_start_sequence=previous_window_final.sequence,
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Latest current final",
        usage=LLMUsage(prompt_tokens=28, completion_tokens=2, total_tokens=30),
        window_tokens=30,
        window_start_sequence=previous_window_final.sequence,
    )

    window = store.list_context_window(context_id=CONTEXT_ID, window_tokens=10)

    assert first_current_final.window_start_sequence == previous_window_final.sequence
    assert [entry.id for entry in window.entries] == [latest.id]


def test_agent_context_store_returns_full_context_without_final_marker(tmp_path) -> None:
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
    store = _store(db_path)

    first = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Task",
    )
    tool_calls = store.append_tool_calls_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="",
    )

    window = store.list_context_window(context_id=CONTEXT_ID, window_tokens=10)

    assert [entry.id for entry in window.entries] == [first.id, tool_calls.id]
