import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from skiller.domain.agent.context.compact_delta import payload_chars
from skiller.domain.agent.context.model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextCompactionQuery,
    AgentContextEntryType,
    AgentContextState,
    AgentContextWindowQuery,
    AgentToolCallPayload,
    AgentUserMessagePayload,
)
from skiller.domain.agent.llm.model import LLMUsage
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.run.identity import AgentContext
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult
from skiller.infrastructure.agent.agent_context_store import AgentContextStore
from skiller.infrastructure.db.datasource.sqlite_agent_context_datasource import (
    SqliteAgentContextDatasource,
)
from skiller.infrastructure.db.datasource.sqlite_agent_context_state_datasource import (
    SqliteAgentContextStateDatasource,
)
from skiller.infrastructure.db.sqlite_run_store_port import SqliteRunStorePort
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap

pytestmark = pytest.mark.unit


def _model(value: str, context_window_tokens: int) -> LLMModelDefinition:
    return LLMModelDefinition(model=value, context_window_tokens=context_window_tokens)


@dataclass(frozen=True)
class _CustomModel:
    value: str
    model_context_window_tokens: int


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
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=100,
            output_tokens=5,
            total_tokens=105,
        ),
        delta_tokens=100,
        compaction_id=None,
    )
    store.append_user_message(context=AGENT_CONTEXT, text="Inspect file")
    store.append_tool_calls_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="I will inspect.",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=190,
            output_tokens=5,
            total_tokens=195,
        ),
        delta_tokens=90,
        compaction_id=1,
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
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=230,
            output_tokens=5,
            total_tokens=235,
        ),
        delta_tokens=40,
        compaction_id=1,
    )




def _set_compact_delta_tokens(
    db_path,
    *,
    sequence: int,
    value: int | None,
    context_id: str = CONTEXT_ID,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE agent_context_entries
            SET delta_compact_tokens = ?
            WHERE context_id = ? AND sequence = ?
            """,
            (value, context_id, sequence),
        )



def _selected_window_tokens(db_path: Path, *, state: AgentContextState) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT COALESCE(
              SUM(
                CASE
                  WHEN sequence <= ? THEN
                    CASE
                      WHEN delta_compact_tokens > 0 THEN delta_compact_tokens
                      ELSE 0
                    END
                  WHEN usage_json IS NOT NULL AND delta_tokens > 0 THEN delta_tokens
                  ELSE 0
                END
              ),
              0
            )
            FROM agent_context_entries
            WHERE context_id = ?
              AND sequence >= ?
            """,
            (
                state.compacted_sequence,
                state.context_id,
                state.start_sequence,
            ),
        ).fetchone()
    assert row is not None
    return int(row[0])

def _append_compaction_selection_block(
    store: AgentContextStore,
    db_path: Path,
    *,
    turn: int,
    raw_tokens: int,
    compact_tokens: int | None,
) -> tuple[int, int]:
    first = store.append_user_message(
        context=AGENT_CONTEXT,
        text=f"User message {turn}",
    )
    marker = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id=f"turn-{turn}",
        text=f"Assistant message {turn}",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=raw_tokens,
            output_tokens=1,
            total_tokens=raw_tokens + 1,
        ),
        delta_tokens=raw_tokens,
        compaction_id=1,
    )
    if compact_tokens is not None:
        _set_compact_delta_tokens(db_path, sequence=first.sequence, value=compact_tokens)
        _set_compact_delta_tokens(db_path, sequence=marker.sequence, value=0)
    return first.sequence, marker.sequence


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
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            prompt_tokens=123,
            output_tokens=45,
            total_tokens=168,
            provider="moonshot",
            model=_model("kimi-k3", 256_000),
        ),
        delta_tokens=123,
        compaction_id=1,
    )

    entries = store.list_entries(context_id=CONTEXT_ID)
    with sqlite3.connect(db_path) as conn:
        raw_row = conn.execute(
            """
            SELECT
              message_type,
              compaction_id,
              delta_tokens,
              delta_compact_tokens,
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
        estimated_system_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        prompt_tokens=123,
        output_tokens=45,
        total_tokens=168,
        provider="moonshot",
        model=_model("kimi-k3", 256_000),
    )
    assert raw_row[0] == "final"
    assert raw_row[1] == 1
    assert raw_row[2] == 123
    assert raw_row[3] is None
    assert raw_row[4] is not None
    assert json.loads(raw_row[4]) == {
        "prompt_tokens": 123,
        "estimated_system_tokens": None,
        "output_tokens": 45,
        "total_tokens": 168,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
        "provider": "moonshot",
        "model": "kimi-k3",
    }
    assert store.get_usage(context_id=CONTEXT_ID) == LLMUsage(
        estimated_system_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        prompt_tokens=123,
        output_tokens=45,
        total_tokens=168,
        provider="moonshot",
        model=_model("kimi-k3", 256_000),
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



def test_agent_context_store_lists_fixed_compact_range_and_prunes_entries(tmp_path) -> None:
    db_path = tmp_path / "agent-context-fixed-compact-range.db"
    store = _store_with_run(db_path)
    _append_compact_fixture(store)
    _set_compact_delta_tokens(db_path, sequence=1, value=30)
    _set_compact_delta_tokens(db_path, sequence=2, value=20)
    _set_compact_delta_tokens(db_path, sequence=3, value=25)
    _set_compact_delta_tokens(db_path, sequence=4, value=15)
    _set_compact_delta_tokens(db_path, sequence=5, value=100)
    _set_compact_delta_tokens(db_path, sequence=6, value=100)
    _set_compact_delta_tokens(db_path, sequence=7, value=10)

    compact = store.list_compact_entries(
        query=AgentContextWindowQuery(
            context_id=CONTEXT_ID,
            start_sequence=2,
            compacted_sequence=7,
        )
    )
    empty = store.list_compact_entries(
        query=AgentContextWindowQuery(
            context_id=CONTEXT_ID,
            start_sequence=8,
            compacted_sequence=7,
        )
    )
    uncompacted = store.list_compact_entries(
        query=AgentContextWindowQuery(
            context_id=CONTEXT_ID,
            start_sequence=1,
            compacted_sequence=None,
        )
    )

    assert [entry.sequence for entry in compact.entries] == [2, 3, 7]
    assert compact.estimated_tokens == 55
    assert empty.entries == []
    assert empty.estimated_tokens == 0
    assert uncompacted.entries == []
    assert uncompacted.estimated_tokens == 0


def test_agent_context_store_returns_empty_compact_range_with_only_prunable_entries(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-only-prunable-compact-range.db"
    store = _store_with_run(db_path)
    _append_compact_fixture(store)

    compact = store.list_compact_entries(
        query=AgentContextWindowQuery(
            context_id=CONTEXT_ID,
            start_sequence=4,
            compacted_sequence=6,
        )
    )

    assert compact.entries == []
    assert compact.estimated_tokens == 0



def test_agent_context_store_keeps_unweighted_compact_entries_at_zero_tokens(tmp_path) -> None:
    db_path = tmp_path / "agent-context-unweighted-compact-entries.db"
    store = _store_with_run(db_path)
    _append_compact_fixture(store)
    _set_compact_delta_tokens(db_path, sequence=1, value=0)
    _set_compact_delta_tokens(db_path, sequence=2, value=-10)
    _set_compact_delta_tokens(db_path, sequence=3, value=30)
    _set_compact_delta_tokens(db_path, sequence=7, value=None)

    compact = store.list_compact_entries(
        query=AgentContextWindowQuery(
            context_id=CONTEXT_ID,
            start_sequence=1,
            compacted_sequence=7,
        )
    )

    assert [entry.sequence for entry in compact.entries] == [1, 2, 3, 7]
    assert compact.estimated_tokens == 30


def test_agent_context_store_lists_fixed_raw_range_without_pruning(tmp_path) -> None:
    db_path = tmp_path / "agent-context-fixed-raw-range.db"
    store = _store_with_run(db_path)
    _append_compact_fixture(store)
    no_prompt_marker = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Usage without prompt tokens",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=None,
            output_tokens=5,
            total_tokens=None,
        ),
        delta_tokens=500,
        compaction_id=None,
    )
    open_entry = store.append_user_message(context=AGENT_CONTEXT, text="Open raw entry")

    raw = store.list_raw_entries(
        query=AgentContextWindowQuery(
            context_id=CONTEXT_ID,
            start_sequence=1,
            compacted_sequence=2,
        )
    )
    empty = store.list_raw_entries(
        query=AgentContextWindowQuery(
            context_id=CONTEXT_ID,
            start_sequence=1,
            compacted_sequence=open_entry.sequence,
        )
    )

    assert [entry.sequence for entry in raw.entries] == [
        3,
        4,
        5,
        6,
        7,
        no_prompt_marker.sequence,
        open_entry.sequence,
    ]
    assert no_prompt_marker.delta_tokens == 500
    assert no_prompt_marker.compaction_id is None
    assert raw.estimated_tokens == 130
    assert empty.entries == []
    assert empty.estimated_tokens == 0


def test_agent_context_store_resolves_raw_start_from_window_state(tmp_path) -> None:
    db_path = tmp_path / "agent-context-raw-window-state.db"
    store = _store_with_run(db_path)
    _append_compact_fixture(store)

    empty_compacted_range = store.list_raw_entries(
        query=AgentContextWindowQuery(
            context_id=CONTEXT_ID,
            start_sequence=5,
            compacted_sequence=4,
        )
    )
    uncompacted = store.list_raw_entries(
        query=AgentContextWindowQuery(
            context_id=CONTEXT_ID,
            start_sequence=5,
            compacted_sequence=None,
        )
    )

    assert [entry.sequence for entry in empty_compacted_range.entries] == [5, 6, 7]
    assert empty_compacted_range.estimated_tokens == 40
    assert [entry.sequence for entry in uncompacted.entries] == [5, 6, 7]
    assert uncompacted.estimated_tokens == 40


def test_agent_context_store_fixed_entry_queries_isolate_contexts(tmp_path) -> None:
    db_path = tmp_path / "agent-context-fixed-ranges-isolation.db"
    store = _store_with_run(db_path)
    _append_compaction_selection_block(
        store,
        db_path,
        turn=1,
        raw_tokens=60,
        compact_tokens=30,
    )
    other_context = AgentContext(
        run_id=RUN_ID,
        agent_id=SOURCE_STEP_ID,
        context_id="thread-2",
    )
    other_user = store.append_user_message(context=other_context, text="Other context")
    other_marker = store.append_final_assistant_message(
        context=other_context,
        turn_id="turn-other",
        text="Other response",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=900,
            output_tokens=1,
            total_tokens=901,
        ),
        delta_tokens=900,
        compaction_id=1,
    )
    _set_compact_delta_tokens(
        db_path,
        context_id=other_context.context_id,
        sequence=other_user.sequence,
        value=450,
    )
    _set_compact_delta_tokens(
        db_path,
        context_id=other_context.context_id,
        sequence=other_marker.sequence,
        value=450,
    )

    raw = store.list_raw_entries(
        query=AgentContextWindowQuery(
            context_id=CONTEXT_ID,
            start_sequence=1,
            compacted_sequence=None,
        )
    )
    compact = store.list_compact_entries(
        query=AgentContextWindowQuery(
            context_id=CONTEXT_ID,
            start_sequence=1,
            compacted_sequence=2,
        )
    )

    assert [entry.context_id for entry in raw.entries] == [CONTEXT_ID, CONTEXT_ID]
    assert raw.estimated_tokens == 60
    assert [entry.context_id for entry in compact.entries] == [CONTEXT_ID, CONTEXT_ID]
    assert compact.estimated_tokens == 30


def test_agent_context_store_selects_compaction_state_with_compact_and_raw_ranges(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-select-compaction.db"
    store = _store_with_run(db_path)
    _append_compaction_selection_block(
        store,
        db_path,
        turn=1,
        raw_tokens=60,
        compact_tokens=30,
    )
    second_start, second_marker = _append_compaction_selection_block(
        store,
        db_path,
        turn=2,
        raw_tokens=50,
        compact_tokens=25,
    )
    _append_compaction_selection_block(
        store,
        db_path,
        turn=3,
        raw_tokens=40,
        compact_tokens=20,
    )
    _append_compaction_selection_block(
        store,
        db_path,
        turn=4,
        raw_tokens=30,
        compact_tokens=15,
    )
    store.append_user_message(context=AGENT_CONTEXT, text="Open raw block")
    query = AgentContextCompactionQuery(
        context_id=CONTEXT_ID,
        start_sequence=1,
        compacted_sequence=None,
        compaction_id=0,
        keep_last_blocks=2,
        target_tokens=100,
    )
    selected = store.select_compaction_state(query=query)

    assert selected == AgentContextState(
        context_id=CONTEXT_ID,
        start_sequence=second_start,
        compacted_sequence=second_marker,
        compaction_id=1,
    )


def test_agent_context_store_reduces_protected_raw_blocks_to_fit_target(tmp_path) -> None:
    db_path = tmp_path / "agent-context-select-reduced-raw.db"
    store = _store_with_run(db_path)
    _append_compaction_selection_block(
        store,
        db_path,
        turn=1,
        raw_tokens=60,
        compact_tokens=30,
    )
    second_start, second_marker = _append_compaction_selection_block(
        store,
        db_path,
        turn=2,
        raw_tokens=50,
        compact_tokens=25,
    )
    _append_compaction_selection_block(
        store,
        db_path,
        turn=3,
        raw_tokens=40,
        compact_tokens=20,
    )
    query = AgentContextCompactionQuery(
        context_id=CONTEXT_ID,
        start_sequence=1,
        compacted_sequence=None,
        compaction_id=0,
        keep_last_blocks=3,
        target_tokens=70,
    )

    selected = store.select_compaction_state(query=query)

    assert selected == AgentContextState(
        context_id=CONTEXT_ID,
        start_sequence=second_start,
        compacted_sequence=second_marker,
        compaction_id=1,
    )
    assert _selected_window_tokens(db_path, state=selected) <= query.target_tokens


def test_agent_context_store_selects_empty_compact_range_when_raw_equals_target(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-select-raw-target.db"
    store = _store_with_run(db_path)
    _append_compaction_selection_block(
        store,
        db_path,
        turn=1,
        raw_tokens=60,
        compact_tokens=30,
    )
    _append_compaction_selection_block(
        store,
        db_path,
        turn=2,
        raw_tokens=50,
        compact_tokens=25,
    )
    raw_start, _ = _append_compaction_selection_block(
        store,
        db_path,
        turn=3,
        raw_tokens=40,
        compact_tokens=20,
    )
    _append_compaction_selection_block(
        store,
        db_path,
        turn=4,
        raw_tokens=30,
        compact_tokens=15,
    )
    query = AgentContextCompactionQuery(
        context_id=CONTEXT_ID,
        start_sequence=1,
        compacted_sequence=None,
        compaction_id=0,
        keep_last_blocks=2,
        target_tokens=70,
    )

    selected = store.select_compaction_state(query=query)

    assert selected == AgentContextState(
        context_id=CONTEXT_ID,
        start_sequence=raw_start,
        compacted_sequence=raw_start - 1,
        compaction_id=1,
    )
    assert _selected_window_tokens(db_path, state=selected) == query.target_tokens


def test_agent_context_store_counts_missing_compact_weights_as_zero(tmp_path) -> None:
    db_path = tmp_path / "agent-context-select-null-weights.db"
    store = _store_with_run(db_path)
    first_start, first_marker = _append_compaction_selection_block(
        store,
        db_path,
        turn=1,
        raw_tokens=60,
        compact_tokens=None,
    )
    _append_compaction_selection_block(
        store,
        db_path,
        turn=2,
        raw_tokens=40,
        compact_tokens=20,
    )
    query = AgentContextCompactionQuery(
        context_id=CONTEXT_ID,
        start_sequence=1,
        compacted_sequence=None,
        compaction_id=0,
        keep_last_blocks=1,
        target_tokens=50,
    )

    selected = store.select_compaction_state(query=query)

    assert selected == AgentContextState(
        context_id=CONTEXT_ID,
        start_sequence=first_start,
        compacted_sequence=first_marker,
        compaction_id=1,
    )


def test_agent_context_store_ignores_open_raw_block_when_selecting_state(tmp_path) -> None:
    db_path = tmp_path / "agent-context-select-open-raw.db"
    store = _store_with_run(db_path)
    _append_compaction_selection_block(
        store,
        db_path,
        turn=1,
        raw_tokens=60,
        compact_tokens=30,
    )
    second_start, second_marker = _append_compaction_selection_block(
        store,
        db_path,
        turn=2,
        raw_tokens=50,
        compact_tokens=25,
    )
    _append_compaction_selection_block(
        store,
        db_path,
        turn=3,
        raw_tokens=40,
        compact_tokens=20,
    )
    query = AgentContextCompactionQuery(
        context_id=CONTEXT_ID,
        start_sequence=1,
        compacted_sequence=None,
        compaction_id=0,
        keep_last_blocks=1,
        target_tokens=70,
    )
    selected_without_open_block = store.select_compaction_state(query=query)
    store.append_user_message(context=AGENT_CONTEXT, text="Open entry 1")
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-open",
        text="Open response without prompt tokens",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=None,
            output_tokens=5,
            total_tokens=None,
        ),
        delta_tokens=500,
        compaction_id=1,
    )
    store.append_user_message(context=AGENT_CONTEXT, text="Open entry 2")

    selected_with_open_block = store.select_compaction_state(query=query)

    expected = AgentContextState(
        context_id=CONTEXT_ID,
        start_sequence=second_start,
        compacted_sequence=second_marker,
        compaction_id=1,
    )
    assert selected_without_open_block == expected
    assert selected_with_open_block == expected


def test_agent_context_store_selects_empty_compact_range_when_latest_raw_is_oversized(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-select-oversized-raw.db"
    store = _store_with_run(db_path)
    _append_compaction_selection_block(
        store,
        db_path,
        turn=1,
        raw_tokens=60,
        compact_tokens=30,
    )
    _append_compaction_selection_block(
        store,
        db_path,
        turn=2,
        raw_tokens=50,
        compact_tokens=25,
    )
    _append_compaction_selection_block(
        store,
        db_path,
        turn=3,
        raw_tokens=40,
        compact_tokens=20,
    )
    latest_start, _ = _append_compaction_selection_block(
        store,
        db_path,
        turn=4,
        raw_tokens=120,
        compact_tokens=15,
    )
    query = AgentContextCompactionQuery(
        context_id=CONTEXT_ID,
        start_sequence=1,
        compacted_sequence=None,
        compaction_id=0,
        keep_last_blocks=2,
        target_tokens=80,
    )

    selected = store.select_compaction_state(query=query)

    assert selected == AgentContextState(
        context_id=CONTEXT_ID,
        start_sequence=latest_start,
        compacted_sequence=latest_start - 1,
        compaction_id=1,
    )


def test_agent_context_store_selects_repeated_compaction_from_current_state(
    tmp_path,
) -> None:
    db_path = tmp_path / "agent-context-select-repeated-compaction.db"
    store = _store_with_run(db_path)
    _append_compaction_selection_block(
        store,
        db_path,
        turn=1,
        raw_tokens=60,
        compact_tokens=30,
    )
    second_start, second_marker = _append_compaction_selection_block(
        store,
        db_path,
        turn=2,
        raw_tokens=50,
        compact_tokens=25,
    )
    third_start, third_marker = _append_compaction_selection_block(
        store,
        db_path,
        turn=3,
        raw_tokens=40,
        compact_tokens=20,
    )
    _append_compaction_selection_block(
        store,
        db_path,
        turn=4,
        raw_tokens=30,
        compact_tokens=15,
    )
    query = AgentContextCompactionQuery(
        context_id=CONTEXT_ID,
        start_sequence=second_start,
        compacted_sequence=second_marker,
        compaction_id=3,
        keep_last_blocks=1,
        target_tokens=70,
    )

    selected = store.select_compaction_state(query=query)

    assert selected == AgentContextState(
        context_id=CONTEXT_ID,
        start_sequence=third_start,
        compacted_sequence=third_marker,
        compaction_id=4,
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
    model = _CustomModel(
        value="google/gemma-4-12b-qat",
        model_context_window_tokens=100_000,
    )

    entry = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-1",
        text="Hello",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            prompt_tokens=123,
            output_tokens=45,
            total_tokens=168,
            provider="lmstudio",
            model=model,
        ),
        delta_tokens=123,
        compaction_id=1,
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
        estimated_system_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        prompt_tokens=123,
        output_tokens=45,
        total_tokens=168,
        provider="lmstudio",
        model="google/gemma-4-12b-qat",
    )
    assert store.get_usage(context_id=CONTEXT_ID) == LLMUsage(
        estimated_system_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        prompt_tokens=123,
        output_tokens=45,
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
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=90,
            output_tokens=5,
            total_tokens=95,
        ),
        delta_tokens=90,
        compaction_id=1,
    )
    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Smaller window task",
    )
    reset = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Reset",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=1,
            output_tokens=1,
            total_tokens=2,
        ),
        delta_tokens=1,
        compaction_id=1,
    )

    entries = store.list_entries(context_id=CONTEXT_ID)

    assert first.delta_tokens == 90
    assert reset.delta_tokens == 1
    assert reset.compaction_id == 1
    assert reset.usage == LLMUsage(
        estimated_system_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        provider=None,
        model=None,
        prompt_tokens=1,
        output_tokens=1,
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
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=90,
            output_tokens=5,
            total_tokens=95,
        ),
        delta_tokens=90,
        compaction_id=1,
    )
    next_final = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Next",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=100,
            output_tokens=5,
            total_tokens=105,
        ),
        delta_tokens=10,
        compaction_id=1,
    )

    assert first.delta_tokens == 90
    assert next_final.delta_tokens == 10


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
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=90,
            output_tokens=5,
            total_tokens=95,
        ),
        delta_tokens=90,
        compaction_id=1,
    )
    start = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current start",
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Current base",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=120,
            output_tokens=5,
            total_tokens=125,
        ),
        delta_tokens=25,
        compaction_id=1,
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Corrupt negative",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=110,
            output_tokens=5,
            total_tokens=115,
        ),
        delta_tokens=-5,
        compaction_id=1,
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
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=130,
            output_tokens=5,
            total_tokens=135,
        ),
        delta_tokens=10,
        compaction_id=1,
    )

    assert (
        store.estimate_window_tokens(
            context_id=CONTEXT_ID,
            start_sequence=start.sequence,
        )
        == 35
    )


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
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=100,
            output_tokens=5,
            total_tokens=105,
        ),
        delta_tokens=100,
        compaction_id=1,
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

    assert (
        store.estimate_delta_tokens(
            context_id=CONTEXT_ID,
            start_sequence=1,
            last_marker_sequence=marker.sequence,
            payload=current_payload,
        )
        == expected_delta_tokens
    )


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
        compaction_id=0,
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

    assert (
        store.estimate_delta_tokens(
            context_id=CONTEXT_ID,
            start_sequence=999,
            last_marker_sequence=999,
            payload=current_payload,
        )
        == expected_delta_tokens
    )




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
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=80,
            output_tokens=5,
            total_tokens=85,
        ),
        delta_tokens=80,
        compaction_id=1,
    )
    current_start = store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current start",
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Old series marker inside current window",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=120,
            output_tokens=5,
            total_tokens=125,
        ),
        delta_tokens=40,
        compaction_id=1,
    )
    store.append_user_message(
        context=AGENT_CONTEXT,
        text="Current tail",
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Current base",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=30,
            output_tokens=5,
            total_tokens=35,
        ),
        delta_tokens=30,
        compaction_id=1,
    )
    SqliteAgentContextStateDatasource(str(db_path)).save_state(
        state=AgentContextState(
            context_id=CONTEXT_ID,
            start_sequence=current_start.sequence,
            compacted_sequence=current_start.sequence - 1,
            compaction_id=1,
        )
    )

    stats = store.get_stats(context_id=CONTEXT_ID)

    assert latest.compaction_id == 1
    assert stats.entries == 6
    assert stats.estimated_tokens == 150
    assert stats.window.start_sequence == current_start.sequence
    assert stats.window.end_sequence == latest.sequence
    assert stats.window.current_tokens == 30



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
        compaction_id=0,
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
        compaction_id=0,
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Done",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=None,
            output_tokens=12,
            total_tokens=None,
        ),
        delta_tokens=0,
        compaction_id=1,
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
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=10,
            output_tokens=5,
            total_tokens=15,
        ),
        delta_tokens=10,
        compaction_id=1,
    )
    store.append_tool_calls_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Not final",
        usage=None,
        delta_tokens=0,
        compaction_id=0,
    )
    latest = store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-3",
        text="Latest final",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=30,
            output_tokens=9,
            total_tokens=39,
        ),
        delta_tokens=20,
        compaction_id=1,
    )

    entries = store.list_entries(context_id=CONTEXT_ID)
    stats = store.get_stats(context_id=CONTEXT_ID)

    assert isinstance(latest.payload, AgentAssistantMessagePayload)
    assert latest.compaction_id == 1
    assert store.get_usage(context_id=CONTEXT_ID) == LLMUsage(
        estimated_system_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        provider=None,
        model=None,
        prompt_tokens=30,
        output_tokens=9,
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
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=10,
            output_tokens=5,
            total_tokens=15,
        ),
        delta_tokens=10,
        compaction_id=1,
    )
    store.append_final_assistant_message(
        context=AGENT_CONTEXT,
        turn_id="turn-2",
        text="Usage without prompt",
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=None,
            output_tokens=5,
            total_tokens=None,
        ),
        delta_tokens=0,
        compaction_id=1,
    )

    marker = store.get_last_usage_marker(context_id=CONTEXT_ID)

    assert marker is not None
    assert marker.sequence == valid.sequence
    assert marker.prompt_tokens == 10
