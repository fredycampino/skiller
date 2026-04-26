import pytest

from skiller.domain.agent_context_model import AgentContextEntryType
from skiller.domain.run_context_model import RunContext
from skiller.infrastructure.db.sqlite_agent_context_store import SqliteAgentContextStore
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore

pytestmark = pytest.mark.unit


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

    first = store.append_entry(
        run_id="run-1",
        context_id="thread-1",
        entry_type=AgentContextEntryType.USER_MESSAGE,
        payload={"type": "user_message", "text": "Hi"},
        source_step_id="support_agent",
        idempotency_key="user:turn-1",
    )
    second = store.append_entry(
        run_id="run-1",
        context_id="thread-1",
        entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
        payload={"type": "assistant_message", "text": "Hello"},
        source_step_id="support_agent",
        idempotency_key="final:turn-1",
    )

    entries = store.list_entries(run_id="run-1", context_id="thread-1")

    assert [entry.id for entry in entries] == [first.id, second.id]
    assert [entry.sequence for entry in entries] == [1, 2]
    assert entries[0].payload == {"type": "user_message", "text": "Hi"}
    assert entries[1].entry_type == AgentContextEntryType.ASSISTANT_MESSAGE


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

    first = store.append_entry(
        run_id="run-1",
        context_id="thread-1",
        entry_type=AgentContextEntryType.USER_MESSAGE,
        payload={"type": "user_message", "text": "Hi"},
        source_step_id="support_agent",
        idempotency_key="user:turn-1",
    )
    duplicate = store.append_entry(
        run_id="run-1",
        context_id="thread-1",
        entry_type=AgentContextEntryType.USER_MESSAGE,
        payload={"type": "user_message", "text": "Ignored"},
        source_step_id="support_agent",
        idempotency_key="user:turn-1",
    )

    entries = store.list_entries(run_id="run-1", context_id="thread-1")

    assert duplicate == first
    assert len(entries) == 1
    assert entries[0].payload == {"type": "user_message", "text": "Hi"}
