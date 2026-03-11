import sqlite3

import pytest

from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore

pytestmark = pytest.mark.unit


def test_init_db_drops_legacy_current_step_column(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE runs (
              id TEXT PRIMARY KEY,
              skill_source TEXT NOT NULL,
              skill_ref TEXT NOT NULL,
              skill_snapshot_json TEXT NOT NULL,
              status TEXT NOT NULL,
              current TEXT,
              current_step INTEGER NOT NULL DEFAULT 0,
              inputs_json TEXT NOT NULL DEFAULT '{}',
              cancel_reason TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT
            );

            INSERT INTO runs (
              id,
              skill_source,
              skill_ref,
              skill_snapshot_json,
              status,
              current,
              current_step,
              inputs_json,
              cancel_reason,
              created_at,
              updated_at
            )
            VALUES (
              'run-1',
              'internal',
              'demo',
              '{"steps":[{"id":"start","type":"notify"}]}',
              'RUNNING',
              'start',
              3,
              '{}',
              NULL,
              '2026-03-11 10:00:00',
              '2026-03-11 10:00:00'
            );
            """
        )

    store = SqliteStateStore(str(db_path))
    store.init_db()

    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()]

    assert "current_step" not in columns

    run = store.get_run("run-1")

    assert run is not None
    assert run.current == "start"
    assert not hasattr(run, "current_step")
