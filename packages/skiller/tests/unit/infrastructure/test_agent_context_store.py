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
from skiller.infrastructure.db.datasource.sqlite_agent_context_datasource import (
    SqliteAgentContextDatasource,
)
from skiller.infrastructure.db.sqlite_run_store_port import SqliteRunStorePort
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap

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
    run_store = SqliteRunStorePort(str(db_path))
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
        delta_tokens=123,
        window_start_sequence=1,
        window_base=True,
    )

    entries = store.list_entries(context_id=CONTEXT_ID)
    with sqlite3.connect(db_path) as conn:
        raw_row = conn.execute(
            """
            SELECT
              message_type,
              window_start_sequence,
              delta_tokens,
              window_base,
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
    assert raw_row[1] == 1
    assert raw_row[2] == 123
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


def test_agent_context_store_persists_delta_markers(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-position-token-reset.db"
    run_store = SqliteRunStorePort(str(db_path))
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
        delta_tokens=90,
        window_start_sequence=1,
        window_base=True,
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
        delta_tokens=1,
        window_start_sequence=reset_start.sequence,
        window_base=True,
    )

    entries = store.list_entries(context_id=CONTEXT_ID)

    assert first.delta_tokens == 90
    assert reset.delta_tokens == 1
    assert reset.window_start_sequence == reset_start.sequence
    assert reset.usage == LLMUsage(
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
    )
    assert [entry.delta_tokens for entry in entries if entry.delta_tokens] == [90, 1]


def test_agent_context_store_keeps_delta_series_markers(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-position-token-delta.db"
    run_store = SqliteRunStorePort(str(db_path))
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
        delta_tokens=90,
        window_start_sequence=1,
        window_base=True,
    )
    next_final = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Next",
        usage=LLMUsage(prompt_tokens=100, completion_tokens=5, total_tokens=105),
        delta_tokens=10,
        window_start_sequence=1,
        window_base=False,
    )

    assert first.delta_tokens == 90
    assert first.window_base is True
    assert next_final.delta_tokens == 10
    assert next_final.window_base is False


def test_agent_context_store_returns_stats_from_latest_usage_marker(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-final-start.db"
    run_store = SqliteRunStorePort(str(db_path))
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
        delta_tokens=35,
        window_start_sequence=1,
        window_base=True,
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
        delta_tokens=25,
        window_start_sequence=3,
        window_base=True,
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Latest current final",
        usage=LLMUsage(prompt_tokens=45, completion_tokens=5, total_tokens=50),
        delta_tokens=20,
        window_start_sequence=3,
        window_base=False,
    )

    stats = store.get_stats(context_id=CONTEXT_ID)
    entries = store.list_window_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=45,
    )

    assert base.delta_tokens == 35
    assert previous.delta_tokens == 25
    assert latest.delta_tokens == 20
    assert latest.window_start_sequence == 3
    assert [entry.sequence for entry in entries] == [3, 4, 5]
    assert stats.entries == 5
    assert stats.estimated_tokens == 80
    assert stats.window.start_sequence == 3
    assert stats.window.end_sequence == 5
    assert stats.window.current_tokens == 45


def test_agent_context_store_keeps_current_window_entries_across_old_series_marker(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-old-series-marker.db"
    run_store = SqliteRunStorePort(str(db_path))
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
        text="Older task",
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Older base",
        usage=LLMUsage(prompt_tokens=80, completion_tokens=5, total_tokens=85),
        delta_tokens=80,
        window_start_sequence=1,
        window_base=True,
    )
    current_start = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current start",
    )
    old_series_inside_window = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Old series marker inside current window",
        usage=LLMUsage(prompt_tokens=120, completion_tokens=5, total_tokens=125),
        delta_tokens=40,
        window_start_sequence=1,
        window_base=True,
    )
    current_tail = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current tail",
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Current base",
        usage=LLMUsage(prompt_tokens=30, completion_tokens=5, total_tokens=35),
        delta_tokens=30,
        window_start_sequence=current_start.sequence,
        window_base=True,
    )

    entries = store.list_window_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=50,
    )

    assert [entry.sequence for entry in entries] == [
        current_start.sequence,
        old_series_inside_window.sequence,
        current_tail.sequence,
        latest.sequence,
    ]


def test_agent_context_store_stops_at_active_window_start_without_base_marker(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-start-without-base-marker.db"
    run_store = SqliteRunStorePort(str(db_path))
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
        text="Older task",
    )
    old_base = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Older base",
        usage=LLMUsage(prompt_tokens=80, completion_tokens=5, total_tokens=85),
        delta_tokens=80,
        window_start_sequence=1,
        window_base=True,
    )
    current_start = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current start",
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Latest current delta",
        usage=LLMUsage(prompt_tokens=35, completion_tokens=5, total_tokens=40),
        delta_tokens=10,
        window_start_sequence=current_start.sequence,
        window_base=False,
    )

    entries = store.list_window_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=50,
    )

    assert old_base.window_base is True
    assert latest.window_base is False
    assert [entry.sequence for entry in entries] == [
        current_start.sequence,
        latest.sequence,
    ]


def test_agent_context_store_stats_uses_latest_usage_marker_prompt_tokens(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-stats-current-series.db"
    run_store = SqliteRunStorePort(str(db_path))
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
        text="Older task",
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Older base",
        usage=LLMUsage(prompt_tokens=80, completion_tokens=5, total_tokens=85),
        delta_tokens=80,
        window_start_sequence=1,
        window_base=True,
    )
    current_start = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current start",
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Old series marker inside current window",
        usage=LLMUsage(prompt_tokens=120, completion_tokens=5, total_tokens=125),
        delta_tokens=40,
        window_start_sequence=1,
        window_base=True,
    )
    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current tail",
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Current base",
        usage=LLMUsage(prompt_tokens=30, completion_tokens=5, total_tokens=35),
        delta_tokens=30,
        window_start_sequence=current_start.sequence,
        window_base=True,
    )

    stats = store.get_stats(context_id=CONTEXT_ID)

    assert latest.window_start_sequence == current_start.sequence
    assert stats.entries == 6
    assert stats.estimated_tokens == 150
    assert stats.window.start_sequence == current_start.sequence
    assert stats.window.end_sequence == latest.sequence
    assert stats.window.current_tokens == 30


def test_agent_context_store_lists_window_entries_across_marker_pages(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-pages.db"
    run_store = SqliteRunStorePort(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = _store(db_path)

    for index in range(120):
        sequence = index + 1
        store.append_final_assistant_message(
            context=AGENT_CONTEXT,
            turn_id=f"turn-{sequence}",
            text=f"Final {sequence}",
            usage=LLMUsage(
                prompt_tokens=sequence,
                completion_tokens=1,
                total_tokens=sequence + 1,
            ),
            delta_tokens=1,
            window_start_sequence=1,
            window_base=sequence == 1,
        )

    entries = store.list_window_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=105,
    )

    assert [entry.sequence for entry in entries] == list(range(16, 121))


def test_agent_context_store_stops_after_oversized_latest_entry(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-oversized-latest.db"
    run_store = SqliteRunStorePort(str(db_path))
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
        text="Older task",
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Latest oversized final",
        usage=LLMUsage(prompt_tokens=80, completion_tokens=1, total_tokens=81),
        delta_tokens=80,
        window_start_sequence=1,
        window_base=True,
    )

    entries = store.list_window_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=50,
    )

    assert [entry.sequence for entry in entries] == [2]


def test_agent_context_store_ignores_negative_delta_when_selecting_window(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-negative-delta.db"
    run_store = SqliteRunStorePort(str(db_path))
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
        text="Older final",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=1, total_tokens=11),
        delta_tokens=10,
        window_start_sequence=1,
        window_base=True,
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Corrupt negative delta",
        usage=LLMUsage(prompt_tokens=5, completion_tokens=1, total_tokens=6),
        delta_tokens=-5,
        window_start_sequence=1,
        window_base=False,
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Latest final",
        usage=LLMUsage(prompt_tokens=15, completion_tokens=1, total_tokens=16),
        delta_tokens=10,
        window_start_sequence=1,
        window_base=False,
    )

    entries = store.list_window_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=15,
    )

    assert [entry.sequence for entry in entries] == [2, 3]


def test_agent_context_store_supports_multiple_tool_calls_in_same_turn(tmp_path) -> None:
    db_path = tmp_path / "agent-context-tools.db"
    run_store = SqliteRunStorePort(str(db_path))
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
    run_store = SqliteRunStorePort(str(db_path))
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
        usage=None,
        delta_tokens=0,
        window_start_sequence=0,
        window_base=False,
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
    run_store = SqliteRunStorePort(str(db_path))
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
        usage=None,
        delta_tokens=0,
        window_start_sequence=0,
        window_base=False,
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Done",
        usage=LLMUsage(prompt_tokens=None, completion_tokens=12, total_tokens=None),
        delta_tokens=0,
        window_start_sequence=1,
        window_base=True,
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
    run_store = SqliteRunStorePort(str(db_path))
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
        delta_tokens=10,
        window_start_sequence=1,
        window_base=True,
    )
    store.append_tool_calls_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Not final",
        usage=None,
        delta_tokens=0,
        window_start_sequence=0,
        window_base=False,
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Latest final",
        usage=LLMUsage(prompt_tokens=30, completion_tokens=9, total_tokens=39),
        delta_tokens=20,
        window_start_sequence=1,
        window_base=False,
    )

    entries = store.list_entries(context_id=CONTEXT_ID)
    stats = store.get_stats(context_id=CONTEXT_ID)

    assert isinstance(latest.payload, AgentAssistantMessagePayload)
    assert latest.window_start_sequence == 1
    assert store.get_usage(context_id=CONTEXT_ID) == LLMUsage(
        prompt_tokens=30,
        completion_tokens=9,
        total_tokens=39,
    )
    assert stats.entries == 3
    assert stats.estimated_tokens == 30
    assert stats.window.start_sequence == 1
    assert stats.window.end_sequence == 3
    assert stats.window.current_tokens == 30
    assert [entry.usage.total_tokens for entry in entries if entry.usage is not None] == [
        15,
        39,
    ]


def test_agent_context_store_skips_usage_without_prompt_for_last_marker(tmp_path) -> None:
    db_path = tmp_path / "agent-context-last-usage-marker.db"
    run_store = SqliteRunStorePort(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    store = _store(db_path)

    valid = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="First final",
        usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        delta_tokens=10,
        window_start_sequence=1,
        window_base=True,
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Usage without prompt",
        usage=LLMUsage(prompt_tokens=None, completion_tokens=5, total_tokens=None),
        delta_tokens=0,
        window_start_sequence=1,
        window_base=False,
    )

    marker = store.get_last_usage_marker(context_id=CONTEXT_ID)

    assert marker is not None
    assert marker.sequence == valid.sequence
    assert marker.prompt_tokens == 10
