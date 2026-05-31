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


def test_sqlite_runtime_bootstrap_rejects_version_mismatch_without_deleting_rows(tmp_path) -> None:
    db_path = tmp_path / "runtime.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE runs (id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO runs (id) VALUES ('run-1')")
        conn.execute("PRAGMA user_version = 1")

    with pytest.raises(RuntimeError, match="Runtime DB version mismatch"):
        SqliteRuntimeBootstrap(str(db_path)).init_db()

    assert _db_version(db_path) == 1
    assert _count_rows(db_path, "runs") == 1


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
