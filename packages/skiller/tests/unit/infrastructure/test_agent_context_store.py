import json
import sqlite3
from pathlib import Path

import pytest

from skiller.domain.agent.context.compact_delta import payload_chars
from skiller.domain.agent.context.model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntryType,
    AgentToolCallPayload,
    AgentUserMessagePayload,
)
from skiller.domain.agent.llm.model import LLMCustomModel, LLMUsage
from skiller.domain.agent.llm.provider_registry import AgentMiniMaxLLMModel
from skiller.domain.agent.run.identity import AgentContext
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


def _store_with_run(db_path) -> AgentContextStore:
    run_store = SqliteRunStorePort(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    return _store(db_path)


def _append_compact_fixture(store: AgentContextStore) -> None:
    store.append_user_message(context=AGENT_CONTEXT, text="Old task")
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Old answer",
        usage=LLMUsage(prompt_tokens=100, completion_tokens=5, total_tokens=105),
        delta_tokens=100,
        window_start_sequence=1,
        window_base=True,
    )
    store.append_user_message(context=AGENT_CONTEXT, text="Inspect file")
    store.append_tool_calls_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="I will inspect.",
        usage=LLMUsage(prompt_tokens=190, completion_tokens=5, total_tokens=195),
        delta_tokens=90,
        window_start_sequence=1,
        window_base=False,
    )
    tool_call = AgentToolCall(
        turn_id="turn-2",
        tool_call_id="call-1",
        tool="read_file",
        parent_sequence=4,
        args={"path": "README.md"},
    )
    store.append_tool_call(context=AGENT_CONTEXT, tool_call=tool_call)
    store.append_tool_result(
        context=AGENT_CONTEXT,
        tool_result=AgentToolResult(
            turn_id="turn-2",
            tool_call_id="call-1",
            parent_sequence=4,
            result=ToolResult(
                name="read_file",
                status=ToolResultStatus.COMPLETED,
                data={"content": "x" * 2000},
                text="x" * 2000,
                error=None,
            ),
        ),
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="File inspected.",
        usage=LLMUsage(prompt_tokens=230, completion_tokens=5, total_tokens=235),
        delta_tokens=40,
        window_start_sequence=1,
        window_base=False,
    )


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
              delta_compact_tokens,
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
    assert entries[1].delta_compact_tokens is None
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
    assert raw_row[3] is None
    assert raw_row[4] == 1
    assert json.loads(raw_row[5]) == {
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


def test_agent_context_store_lists_entries_from_sequence(tmp_path) -> None:
    db_path = tmp_path / "agent-context-from-sequence.db"
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

    store.append_user_message(context=AGENT_CONTEXT, text="First")
    second = store.append_user_message(context=AGENT_CONTEXT, text="Second")
    third = store.append_user_message(context=AGENT_CONTEXT, text="Third")

    entries = store.list_entries_from_sequence(
        context_id=CONTEXT_ID,
        start_sequence=second.sequence,
    )

    assert [entry.sequence for entry in entries] == [second.sequence, third.sequence]


def test_sqlite_agent_context_datasource_lists_protected_tail_by_blocks(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-protected-tail.db"
    store = _store_with_run(db_path)
    datasource = SqliteAgentContextDatasource(str(db_path))
    _append_compact_fixture(store)

    latest_block = datasource.list_protected_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=40,
        keep_last_blocks=1,
    )
    large_window_tail = datasource.list_protected_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=130,
        keep_last_blocks=1,
    )
    two_blocks_small_window_tail = datasource.list_protected_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=40,
        keep_last_blocks=2,
    )
    two_blocks_tail = datasource.list_protected_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=130,
        keep_last_blocks=2,
    )
    latest_block_over_window = datasource.list_protected_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=30,
        keep_last_blocks=2,
    )
    oversized_window_tail = datasource.list_protected_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=500,
        keep_last_blocks=1,
    )

    assert [entry.sequence for entry in latest_block.entries] == [5, 6, 7]
    assert latest_block.tokens == 40
    assert [entry.sequence for entry in large_window_tail.entries] == [5, 6, 7]
    assert large_window_tail.tokens == 40
    assert [entry.sequence for entry in two_blocks_small_window_tail.entries] == [
        5,
        6,
        7,
    ]
    assert two_blocks_small_window_tail.tokens == 40
    assert [entry.sequence for entry in two_blocks_tail.entries] == [3, 4, 5, 6, 7]
    assert two_blocks_tail.tokens == 130
    assert [entry.sequence for entry in latest_block_over_window.entries] == [
        5,
        6,
        7,
    ]
    assert latest_block_over_window.tokens == 40
    assert [entry.sequence for entry in oversized_window_tail.entries] == [5, 6, 7]
    assert oversized_window_tail.tokens == 40


def test_sqlite_agent_context_datasource_protected_tail_keeps_blocks_that_fit(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-protected-tail-fit.db"
    store = _store_with_run(db_path)
    datasource = SqliteAgentContextDatasource(str(db_path))

    for index, delta_tokens in enumerate((10, 20, 20, 15, 40, 50), 1):
        store.append_final_assistant_message(
            context=AGENT_CONTEXT,
            turn_id=f"turn-{index}",
            text=f"block {index}",
            usage=LLMUsage(
                prompt_tokens=delta_tokens,
                completion_tokens=1,
                total_tokens=delta_tokens + 1,
            ),
            delta_tokens=delta_tokens,
            window_start_sequence=1,
            window_base=index == 1,
        )

    protected = datasource.list_protected_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=100,
        keep_last_blocks=5,
    )
    max_blocks = datasource.list_protected_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=200,
        keep_last_blocks=5,
    )

    assert [entry.sequence for entry in protected.entries] == [5, 6]
    assert protected.tokens == 90
    assert [entry.sequence for entry in max_blocks.entries] == [2, 3, 4, 5, 6]
    assert max_blocks.tokens == 145


def test_sqlite_agent_context_datasource_returns_empty_protected_entries_without_usage(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-protected-empty.db"
    store = _store_with_run(db_path)
    datasource = SqliteAgentContextDatasource(str(db_path))
    store.append_user_message(context=AGENT_CONTEXT, text="First")
    store.append_user_message(context=AGENT_CONTEXT, text="Second")

    protected = datasource.list_protected_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=100,
        keep_last_blocks=1,
    )

    assert protected.entries == []
    assert protected.tokens == 0


def test_sqlite_agent_context_datasource_lists_compact_entries_from_sequence(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-compact-list.db"
    store = _store_with_run(db_path)
    datasource = SqliteAgentContextDatasource(str(db_path))
    _append_compact_fixture(store)
    _set_compact_delta_tokens(db_path, sequence=1, value=20)
    _set_compact_delta_tokens(db_path, sequence=2, value=30)
    _set_compact_delta_tokens(db_path, sequence=3, value=35)
    _set_compact_delta_tokens(db_path, sequence=7, value=40)

    entries_before_tools = datasource.list_compact_entries(
        context_id=CONTEXT_ID,
        start_sequence=6,
        window_width_tokens=65,
    )
    entries_with_pruned_tools = datasource.list_compact_entries(
        context_id=CONTEXT_ID,
        start_sequence=7,
        window_width_tokens=75,
    )
    empty_when_first_marker_exceeds_budget = (
        datasource.list_compact_entries(
            context_id=CONTEXT_ID,
            start_sequence=7,
            window_width_tokens=30,
        )
    )
    empty_without_compact_markers = datasource.list_compact_entries(
        context_id=CONTEXT_ID,
        start_sequence=0,
        window_width_tokens=100,
    )

    assert [entry.sequence for entry in entries_before_tools] == [2, 3]
    assert [entry.sequence for entry in entries_with_pruned_tools] == [3, 7]
    assert empty_when_first_marker_exceeds_budget == []
    assert empty_without_compact_markers == []


def test_sqlite_agent_context_datasource_compact_and_protected_ranges_do_not_overlap(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-compact-protected-boundary.db"
    store = _store_with_run(db_path)
    datasource = SqliteAgentContextDatasource(str(db_path))
    _append_compact_fixture(store)
    _set_compact_delta_tokens(db_path, sequence=1, value=20)
    _set_compact_delta_tokens(db_path, sequence=2, value=30)
    _set_compact_delta_tokens(db_path, sequence=3, value=35)

    protected = datasource.list_protected_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=40,
        keep_last_blocks=1,
    )
    compact = datasource.list_compact_entries(
        context_id=CONTEXT_ID,
        start_sequence=protected.entries[0].sequence - 1,
        window_width_tokens=85,
    )

    assert [entry.sequence for entry in compact] == [1, 2, 3]
    assert [entry.sequence for entry in protected.entries] == [5, 6, 7]
    assert compact[-1].sequence < protected.entries[0].sequence


def test_agent_context_store_lists_all_entries_without_usage_markers(tmp_path) -> None:
    db_path = tmp_path / "agent-context-compact-without-usage.db"
    store = _store_with_run(db_path)
    first = store.append_user_message(context=AGENT_CONTEXT, text="First")
    second = store.append_user_message(context=AGENT_CONTEXT, text="Second")

    entries = store.list_compact_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=100,
        keep_last_blocks=1,
    )

    assert [entry.sequence for entry in entries] == [first.sequence, second.sequence]


def test_agent_context_store_returns_empty_compact_entries_for_empty_context(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-compact-empty.db"
    store = _store_with_run(db_path)

    entries = store.list_compact_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=100,
        keep_last_blocks=1,
    )

    assert entries == []


def test_agent_context_store_adds_compact_delta_tokens_to_non_prunable_entries(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-compact-delta-markers.db"
    store = _store_with_run(db_path)

    first_user = store.append_user_message(context=AGENT_CONTEXT, text="Inspect files")
    first_marker = store.append_tool_calls_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="I will inspect.",
        usage=LLMUsage(prompt_tokens=90, completion_tokens=5, total_tokens=95),
        delta_tokens=90,
        window_start_sequence=1,
        window_base=True,
    )
    store.add_compact_delta_tokens(
        context_id=CONTEXT_ID,
        marker_sequence=first_marker.sequence,
    )
    tool_call = store.append_tool_call(
        context=AGENT_CONTEXT,
        tool_call=AgentToolCall(
            turn_id="turn-1",
            parent_sequence=first_marker.sequence,
            tool_call_id="call-1",
            tool="read_file",
            args={"path": "README.md"},
        ),
    )
    tool_result = store.append_tool_result(
        context=AGENT_CONTEXT,
        tool_result=AgentToolResult(
            turn_id="turn-1",
            tool_call_id="call-1",
            parent_sequence=first_marker.sequence,
            result=ToolResult(
                name="read_file",
                status=ToolResultStatus.COMPLETED,
                data={"content": "x" * 200},
                text="x" * 200,
                error=None,
            ),
        ),
    )
    final_marker = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="File inspected.",
        usage=LLMUsage(prompt_tokens=200, completion_tokens=5, total_tokens=205),
        delta_tokens=110,
        window_start_sequence=1,
        window_base=False,
    )
    store.add_compact_delta_tokens(
        context_id=CONTEXT_ID,
        marker_sequence=final_marker.sequence,
    )
    first_block_chars = payload_chars(first_user.payload) + payload_chars(
        first_marker.payload
    )
    tool_block_chars = (
        payload_chars(tool_call.payload)
        + payload_chars(tool_result.payload)
        + payload_chars(final_marker.payload)
    )

    assert _compact_delta_tokens(db_path, sequence=first_user.sequence) == round(
        90 * payload_chars(first_user.payload) / first_block_chars
    )
    assert _compact_delta_tokens(db_path, sequence=first_marker.sequence) is None
    assert _compact_delta_tokens(db_path, sequence=tool_call.sequence) is None
    assert _compact_delta_tokens(db_path, sequence=tool_result.sequence) is None
    assert _compact_delta_tokens(db_path, sequence=final_marker.sequence) == round(
        110 * payload_chars(final_marker.payload) / tool_block_chars
    )
    assert [entry.delta_tokens for entry in store.list_entries(context_id=CONTEXT_ID)] == [
        None,
        90,
        None,
        None,
        110,
    ]


def test_agent_context_store_lists_compact_entries_with_protected_tail(tmp_path) -> None:
    db_path = tmp_path / "agent-context-compact-window.db"
    store = _store_with_run(db_path)
    _append_compact_fixture(store)

    entries = store.list_compact_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=130,
        keep_last_blocks=1,
    )

    assert [entry.sequence for entry in entries] == [5, 6, 7]
    assert entries[0].entry_type == AgentContextEntryType.TOOL_CALL
    assert entries[1].entry_type == AgentContextEntryType.TOOL_RESULT


def test_agent_context_store_compact_entries_match_normal_window_when_tail_fills(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-compact-window-tail.db"
    store = _store_with_run(db_path)
    _append_compact_fixture(store)

    compact_entries = store.list_compact_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=40,
        keep_last_blocks=1,
    )
    normal_entries = store.list_window_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=40,
    )

    assert [entry.sequence for entry in compact_entries] == [
        entry.sequence for entry in normal_entries
    ]


def test_agent_context_store_keeps_maximum_protected_blocks_when_they_fit(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-compact-window-min-blocks.db"
    store = _store_with_run(db_path)
    _append_compact_fixture(store)

    entries = store.list_compact_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=130,
        keep_last_blocks=2,
    )

    assert [entry.sequence for entry in entries] == [3, 4, 5, 6, 7]


def test_agent_context_store_keeps_only_protected_blocks_that_fit_window(tmp_path) -> None:
    db_path = tmp_path / "agent-context-compact-window-fit-blocks.db"
    store = _store_with_run(db_path)
    _append_compact_fixture(store)

    entries = store.list_compact_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=40,
        keep_last_blocks=2,
    )

    assert [entry.sequence for entry in entries] == [5, 6, 7]


def test_agent_context_store_normalizes_compact_keep_last_blocks(tmp_path) -> None:
    db_path = tmp_path / "agent-context-compact-window-normalize.db"
    store = _store_with_run(db_path)
    _append_compact_fixture(store)

    below_min = store.list_compact_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=130,
        keep_last_blocks=0,
    )
    min_value = store.list_compact_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=130,
        keep_last_blocks=1,
    )
    above_max = store.list_compact_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=130,
        keep_last_blocks=101,
    )
    max_value = store.list_compact_entries(
        context_id=CONTEXT_ID,
        window_width_tokens=130,
        keep_last_blocks=100,
    )

    assert [entry.sequence for entry in below_min] == [
        entry.sequence for entry in min_value
    ]
    assert [entry.sequence for entry in above_max] == [
        entry.sequence for entry in max_value
    ]


def _compact_delta_tokens(db_path: Path, *, sequence: int) -> int | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT delta_compact_tokens
            FROM agent_context_entries
            WHERE context_id = ? AND sequence = ?
            """,
            (CONTEXT_ID, sequence),
        ).fetchone()
    assert row is not None
    return row[0]


def _set_compact_delta_tokens(db_path: Path, *, sequence: int, value: int) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE agent_context_entries
            SET delta_compact_tokens = ?
            WHERE context_id = ? AND sequence = ?
            """,
            (value, CONTEXT_ID, sequence),
        )


def test_agent_context_store_persists_custom_usage_model_name(tmp_path) -> None:
    db_path = tmp_path / "agent-context-custom-model.db"
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
    model = LLMCustomModel(
        value="google/gemma-4-12b-qat",
        model_context_window_tokens=100_000,
    )

    entry = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Hello",
        usage=LLMUsage(
            prompt_tokens=123,
            completion_tokens=45,
            total_tokens=168,
            provider="lmstudio",
            model=model,
        ),
        delta_tokens=123,
        window_start_sequence=1,
        window_base=True,
    )

    entries = store.list_entries(context_id=CONTEXT_ID)
    with sqlite3.connect(db_path) as conn:
        raw_usage = conn.execute(
            """
            SELECT usage_json
            FROM agent_context_entries
            WHERE id = ?
            """,
            (entry.id,),
        ).fetchone()[0]

    assert json.loads(raw_usage)["model"] == "google/gemma-4-12b-qat"
    assert entries[0].usage == LLMUsage(
        prompt_tokens=123,
        completion_tokens=45,
        total_tokens=168,
        provider="lmstudio",
        model="google/gemma-4-12b-qat",
    )
    assert store.get_usage(context_id=CONTEXT_ID) == LLMUsage(
        prompt_tokens=123,
        completion_tokens=45,
        total_tokens=168,
        provider="lmstudio",
        model="google/gemma-4-12b-qat",
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


def test_agent_context_store_estimates_window_tokens_from_start_sequence(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-estimate.db"
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
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Older",
        usage=LLMUsage(prompt_tokens=90, completion_tokens=5, total_tokens=95),
        delta_tokens=90,
        window_start_sequence=1,
        window_base=True,
    )
    start = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current start",
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Current base",
        usage=LLMUsage(prompt_tokens=120, completion_tokens=5, total_tokens=125),
        delta_tokens=25,
        window_start_sequence=start.sequence,
        window_base=True,
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Corrupt negative",
        usage=LLMUsage(prompt_tokens=110, completion_tokens=5, total_tokens=115),
        delta_tokens=-5,
        window_start_sequence=start.sequence,
        window_base=False,
    )
    store.append_tool_call(
        context=AGENT_CONTEXT,
        tool_call=AgentToolCall(
            turn_id="turn-3",
            parent_sequence=None,
            tool_call_id="call-1",
            tool="notify",
            args={"message": "ok"},
        ),
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-4",
        text="Tail",
        usage=LLMUsage(prompt_tokens=130, completion_tokens=5, total_tokens=135),
        delta_tokens=10,
        window_start_sequence=start.sequence,
        window_base=False,
    )

    assert store.estimate_window_tokens(
        context_id=CONTEXT_ID,
        start_sequence=start.sequence,
    ) == 35


def test_agent_context_store_estimates_delta_tokens_from_payload_chars(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-delta-estimate.db"
    store = _store_with_run(db_path)

    store.append_user_message(context=AGENT_CONTEXT, text="Old task " * 20)
    marker = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Old answer " * 20,
        usage=LLMUsage(prompt_tokens=100, completion_tokens=5, total_tokens=105),
        delta_tokens=100,
        window_start_sequence=1,
        window_base=True,
    )
    store.append_user_message(context=AGENT_CONTEXT, text="Current task " * 10)
    current_payload = AgentAssistantMessagePayload(
        turn_id="turn-2",
        message_type=AgentAssistantMessageType.TOOL_CALLS,
        text="Inspecting.",
    )
    persisted_block_chars = store.datasource.payload_chars_from_sequence(
        context_id=CONTEXT_ID,
        start_sequence=marker.sequence + 1,
    )
    block_chars = persisted_block_chars + payload_chars(current_payload)
    expected_delta_tokens = max(1, (block_chars + 1) // 3)

    assert store.estimate_delta_tokens(
        context_id=CONTEXT_ID,
        window_start_sequence=1,
        last_marker_sequence=marker.sequence,
        payload=current_payload,
    ) == expected_delta_tokens


def test_sqlite_agent_context_datasource_sums_payload_chars_from_sequence(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-payload-chars.db"
    store = _store_with_run(db_path)

    store.append_user_message(context=AGENT_CONTEXT, text="Ignored")
    start = store.append_user_message(context=AGENT_CONTEXT, text="Start")
    final = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Final",
        usage=None,
        delta_tokens=0,
        window_start_sequence=0,
        window_base=False,
    )

    assert store.datasource.payload_chars_from_sequence(
        context_id=CONTEXT_ID,
        start_sequence=start.sequence,
    ) == payload_chars(start.payload) + payload_chars(final.payload)


def test_agent_context_store_estimates_delta_tokens_from_current_payload(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-delta-estimate-current-payload.db"
    store = _store_with_run(db_path)
    current_payload = AgentAssistantMessagePayload(
        turn_id="turn-1",
        message_type=AgentAssistantMessageType.FINAL,
        text="Done.",
    )
    block_chars = payload_chars(current_payload)
    expected_delta_tokens = max(1, (block_chars + 1) // 3)

    assert store.estimate_delta_tokens(
        context_id=CONTEXT_ID,
        window_start_sequence=999,
        last_marker_sequence=999,
        payload=current_payload,
    ) == expected_delta_tokens


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


def test_sqlite_agent_context_datasource_window_start_sequence_from_token_limit(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-start-query.db"
    run_store = SqliteRunStorePort(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    datasource = SqliteAgentContextDatasource(str(db_path))
    store = AgentContextStore(datasource)

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
        text="Old series inside current window",
        usage=LLMUsage(prompt_tokens=120, completion_tokens=5, total_tokens=125),
        delta_tokens=40,
        window_start_sequence=1,
        window_base=True,
    )
    current_tail = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current tail",
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Current base",
        usage=LLMUsage(prompt_tokens=30, completion_tokens=5, total_tokens=35),
        delta_tokens=30,
        window_start_sequence=current_start.sequence,
        window_base=True,
    )

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        start_sequence = datasource.window_start_sequence(
            conn,
            context_id=CONTEXT_ID,
            window_width_tokens=50,
        )

    assert start_sequence == current_tail.sequence


def test_sqlite_agent_context_datasource_window_start_sequence_keeps_oversized_latest(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-window-start-oversized.db"
    run_store = SqliteRunStorePort(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=RUN_ID,
    )
    datasource = SqliteAgentContextDatasource(str(db_path))
    store = AgentContextStore(datasource)

    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Older task",
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Oversized",
        usage=LLMUsage(prompt_tokens=80, completion_tokens=5, total_tokens=85),
        delta_tokens=80,
        window_start_sequence=1,
        window_base=True,
    )

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        start_sequence = datasource.window_start_sequence(
            conn,
            context_id=CONTEXT_ID,
            window_width_tokens=50,
        )

    assert start_sequence == latest.sequence


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
