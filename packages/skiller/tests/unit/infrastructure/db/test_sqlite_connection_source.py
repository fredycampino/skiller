import sqlite3
from pathlib import Path

import pytest

from skiller.infrastructure.db.datasource.sqlite_connection_source import SqliteConnectionSource
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap
from skiller.infrastructure.db.sqlite_runtime_event_store import SqliteRuntimeEventStore

pytestmark = pytest.mark.unit


def test_connection_commits_and_closes(tmp_path: Path) -> None:
    source = SqliteConnectionSource(str(tmp_path / "runtime.db"))

    with source._connect() as conn:
        conn.execute("CREATE TABLE items (value TEXT)")
        conn.execute("INSERT INTO items VALUES ('saved')")
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    with source._connect() as reader:
        assert reader.execute("SELECT value FROM items").fetchone()["value"] == "saved"


def test_connection_rolls_back_and_closes_on_error(tmp_path: Path) -> None:
    source = SqliteConnectionSource(str(tmp_path / "runtime.db"))
    with source._connect() as setup:
        setup.execute("CREATE TABLE items (value TEXT)")

    with pytest.raises(ValueError, match="abort"):
        with source._connect() as conn:
            conn.execute("INSERT INTO items VALUES ('discarded')")
            raise ValueError("abort")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    with source._connect() as reader:
        assert reader.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0


def test_repeated_event_queries_and_bootstrap_close_every_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connections: list[sqlite3.Connection] = []
    connect = sqlite3.connect

    def track_connect(path: str | Path) -> sqlite3.Connection:
        connection = connect(path)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", track_connect)
    path = str(tmp_path / "runtime.db")
    bootstrap = SqliteRuntimeBootstrap(path)
    bootstrap.init_db()
    bootstrap.init_db()
    store = SqliteRuntimeEventStore(path)

    for _ in range(100):
        assert store.list_events("missing-run") == []
        assert store.get_last_event("missing-run") is None

    assert len(connections) >= 200
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
