import sqlite3

import pytest

from skiller.domain.agent.context.model import AgentContextState
from skiller.infrastructure.db.datasource.sqlite_agent_context_state_datasource import (
    SqliteAgentContextStateDatasource,
)
from skiller.infrastructure.db.sqlite_agent_context_state_port import (
    SqliteAgentContextStatePort,
)
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap

pytestmark = pytest.mark.unit


def _state_port(db_path) -> SqliteAgentContextStatePort:
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    datasource = SqliteAgentContextStateDatasource(str(db_path))
    return SqliteAgentContextStatePort(datasource)


def test_sqlite_agent_context_state_port_returns_initial_state_without_state(tmp_path) -> None:
    state_port = _state_port(tmp_path / "runtime.db")

    state = state_port.get_state(context_id="context-1")

    assert state == AgentContextState(
        context_id="context-1",
        start_sequence=1,
        compacted_sequence=None,
        compaction_id=0,
    )


def test_sqlite_agent_context_state_port_saves_and_updates_state_atomically(tmp_path) -> None:
    db_path = tmp_path / "runtime.db"
    state_port = _state_port(db_path)
    initial = AgentContextState(
        context_id="context-1",
        start_sequence=1,
        compacted_sequence=None,
        compaction_id=0,
    )
    compacted = AgentContextState(
        context_id="context-1",
        start_sequence=3,
        compacted_sequence=7,
        compaction_id=1,
    )

    state_port.save_state(state=initial)
    assert state_port.get_state(context_id="context-1") == initial

    state_port.save_state(state=compacted)

    assert state_port.get_state(context_id="context-1") == compacted
    with sqlite3.connect(db_path) as conn:
        row_count = conn.execute(
            "SELECT COUNT(*) FROM agent_context_state WHERE context_id = ?",
            ("context-1",),
        ).fetchone()
    assert row_count == (1,)


def test_sqlite_agent_context_state_port_keeps_previous_state_when_save_fails(
    tmp_path,
) -> None:
    state_port = _state_port(tmp_path / "runtime.db")
    previous = AgentContextState(
        context_id="context-1",
        start_sequence=3,
        compacted_sequence=7,
        compaction_id=1,
    )
    invalid = AgentContextState(
        context_id="context-1",
        start_sequence=8,
        compacted_sequence=3,
        compaction_id=2,
    )
    state_port.save_state(state=previous)

    with pytest.raises(sqlite3.IntegrityError):
        state_port.save_state(state=invalid)

    assert state_port.get_state(context_id="context-1") == previous
