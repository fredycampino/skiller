import sqlite3

import pytest

from skiller.infrastructure.db.sqlite_runtime_bootstrap import (
    SQLITE_RUNTIME_DB_VERSION,
    SqliteRuntimeBootstrap,
)

pytestmark = pytest.mark.unit


def test_sqlite_runtime_bootstrap_creates_schema_and_sets_db_version(tmp_path) -> None:
    db_path = tmp_path / "runtime.db"

    SqliteRuntimeBootstrap(str(db_path)).init_db()

    assert _db_version(db_path) == SQLITE_RUNTIME_DB_VERSION
    assert _table_exists(db_path, "runs") is True
    assert _table_exists(db_path, "agent_context_entries") is True
    assert _table_exists(db_path, "webhook_registrations") is True
    assert _table_columns(db_path, "webhook_registrations") >= {
        "webhook",
        "secret",
        "method",
        "auth",
        "payload_source",
        "enabled",
        "created_at",
    }


def test_sqlite_runtime_bootstrap_resets_version_mismatch(tmp_path) -> None:
    db_path = tmp_path / "runtime.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE runs (id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO runs (id) VALUES ('run-1')")
        conn.execute("PRAGMA user_version = 1")

    SqliteRuntimeBootstrap(str(db_path)).init_db()

    assert _db_version(db_path) == SQLITE_RUNTIME_DB_VERSION
    assert _count_rows(db_path, "runs") == 0


def test_sqlite_runtime_bootstrap_resets_v6_agent_context_schema(tmp_path) -> None:
    db_path = tmp_path / "runtime.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE runs (
              id TEXT PRIMARY KEY,
              source TEXT NOT NULL,
              ref TEXT NOT NULL,
              snapshot_json TEXT NOT NULL,
              status TEXT NOT NULL,
              current TEXT,
              inputs_json TEXT NOT NULL DEFAULT '{}',
              step_executions_json TEXT NOT NULL DEFAULT '{}',
              agents_json TEXT NOT NULL DEFAULT '{}',
              steering_queue_json TEXT NOT NULL DEFAULT '[]',
              cancel_reason TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT
            );
            CREATE TABLE agent_context_entries (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              context_id TEXT NOT NULL,
              sequence INTEGER NOT NULL,
              entry_type TEXT NOT NULL,
              message_type TEXT NULL,
              window_start_sequence INTEGER NULL,
              position_tokens INTEGER NULL,
              window_tokens INTEGER NULL,
              payload_json TEXT NOT NULL,
              usage_json TEXT NULL,
              source_step_id TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO runs (
              id,
              source,
              ref,
              snapshot_json,
              status,
              inputs_json,
              step_executions_json
            )
            VALUES (
              'run-1',
              'internal',
              'demo',
              '{}',
              'RUNNING',
              '{}',
              '{}'
            );
            INSERT INTO agent_context_entries (
              id,
              run_id,
              context_id,
              sequence,
              entry_type,
              message_type,
              window_start_sequence,
              position_tokens,
              window_tokens,
              payload_json,
              usage_json,
              source_step_id
            )
            VALUES (
              'entry-1',
              'run-1',
              'ctx-1',
              1,
              'assistant_message',
              'final',
              1,
              120,
              80,
              '{"type":"assistant_message","turn_id":"turn-1","message_type":"final","text":"ok"}',
              '{"prompt_tokens":120,"completion_tokens":10,"total_tokens":130}',
              'support_agent'
            );
            PRAGMA user_version = 6;
            """
        )

    SqliteRuntimeBootstrap(str(db_path)).init_db()

    columns = _table_columns(db_path, "agent_context_entries")
    assert _db_version(db_path) == SQLITE_RUNTIME_DB_VERSION
    assert "delta_tokens" in columns
    assert "window_base" in columns
    assert "position_tokens" not in columns
    assert "window_tokens" not in columns
    assert _count_rows(db_path, "agent_context_entries") == 0


def _db_version(db_path) -> int:  # noqa: ANN001
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("PRAGMA user_version").fetchone()
    assert row is not None
    return int(row[0])


def _table_exists(db_path, table: str) -> bool:  # noqa: ANN001
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table,),
        ).fetchone()
    return row is not None


def _count_rows(db_path, table: str) -> int:  # noqa: ANN001
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])


def _table_columns(db_path, table: str) -> set[str]:  # noqa: ANN001
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}
