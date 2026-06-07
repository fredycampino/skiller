import pytest

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import RunAgentWindow
from skiller.infrastructure.db.datasource.sqlite_run_agent_datasource import (
    SqliteRunAgentDatasource,
)
from skiller.infrastructure.db.sqlite_run_agent_store import SqliteRunAgentStore
from skiller.infrastructure.db.sqlite_run_store_port import SqliteRunStorePort
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap

pytestmark = pytest.mark.unit


def test_run_agent_store_updates_agent_window_without_losing_context(tmp_path) -> None:
    db_path = tmp_path / "run-agents.db"
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    run_store = SqliteRunStorePort(str(db_path))
    agent_store = SqliteRunAgentStore(SqliteRunAgentDatasource(str(db_path)))
    run_id = "550e8400-e29b-41d4-a716-446655440006"
    run_store.create_run(
        "internal",
        "demo",
        {"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=run_id,
    )

    assert agent_store.get_agent(run_id=run_id, agent_id="support_agent") is None

    agent_store.attach_agent(
        run_id=run_id,
        agent_id="support_agent",
        context_id="thread-123",
    )

    agent = agent_store.get_agent(run_id=run_id, agent_id="support_agent")
    run = run_store.get_run(run_id)

    assert agent is not None
    assert agent.agent_id == "support_agent"
    assert agent.context_id == "thread-123"
    assert agent.window_start_sequence == 0
    assert agent.window_base is True
    assert run is not None
    assert run.agents["support_agent"].context_id == "thread-123"
    assert run.agents["support_agent"].window_start_sequence == 0
    assert run.agents["support_agent"].window_base is True

    agent_store.update_agent_window(
        run_id=run_id,
        window=RunAgentWindow(
            agent_id="support_agent",
            window_start_sequence=7,
            window_base=False,
        ),
    )

    stored_agent = agent_store.get_agent(run_id=run_id, agent_id="support_agent")
    stored_run = run_store.get_run(run_id)
    assert stored_agent is not None
    assert stored_agent.context_id == "thread-123"
    assert stored_agent.window_start_sequence == 7
    assert stored_agent.window_base is False
    assert stored_run is not None
    assert stored_run.agents["support_agent"].context_id == "thread-123"
    assert stored_run.agents["support_agent"].window_start_sequence == 7
    assert stored_run.agents["support_agent"].window_base is False

    agent_store.attach_agent(
        run_id=run_id,
        agent_id="support_agent",
        context_id="thread-456",
    )

    updated_agent = agent_store.get_agent(run_id=run_id, agent_id="support_agent")
    assert updated_agent is not None
    assert updated_agent.context_id == "thread-456"
    assert updated_agent.window_start_sequence == 7
    assert updated_agent.window_base is False
