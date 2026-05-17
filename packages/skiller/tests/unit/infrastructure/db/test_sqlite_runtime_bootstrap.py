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


def test_sqlite_runtime_bootstrap_resets_outdated_database(tmp_path) -> None:
    db_path = tmp_path / "runtime.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE runs (id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO runs (id) VALUES ('run-1')")

    SqliteRuntimeBootstrap(str(db_path)).init_db()

    assert _db_version(db_path) == SQLITE_RUNTIME_DB_VERSION
    assert _count_rows(db_path, "runs") == 0


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
