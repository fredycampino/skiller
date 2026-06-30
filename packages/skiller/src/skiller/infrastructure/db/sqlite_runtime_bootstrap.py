import sqlite3
from pathlib import Path

from skiller.domain.run.runtime_bootstrap_port import RuntimeBootstrapPort
from skiller.infrastructure.db.datasource.sqlite_connection_source import SqliteConnectionSource

SQLITE_RUNTIME_DB_VERSION = 8


class SqliteRuntimeBootstrap(SqliteConnectionSource, RuntimeBootstrapPort):
    def init_db(self) -> None:
        db_path = Path(self.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if _should_reset_db(db_path):
            _delete_db_files(db_path)
        with self._connect() as conn:
            apply_db_updates(conn, db_path=self.db_path)
            _create_runtime_schema(conn)


def apply_db_updates(conn: sqlite3.Connection, *, db_path: str) -> None:
    current_version = _db_version(conn)
    if current_version == SQLITE_RUNTIME_DB_VERSION:
        return
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        """
    ).fetchone()
    table_count = int(row[0]) if row is not None else 0
    if current_version == 0 and table_count == 0:
        _set_db_version(conn, SQLITE_RUNTIME_DB_VERSION)
        return
    if current_version == 7:
        _upgrade_v7_to_v8(conn)
        _set_db_version(conn, SQLITE_RUNTIME_DB_VERSION)
        return
    raise RuntimeError(
        "Runtime DB version mismatch: "
        f"db={current_version}, expected={SQLITE_RUNTIME_DB_VERSION}, path={db_path}"
    )


def _upgrade_v7_to_v8(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, table="agent_context_entries")
    if "delta_compact_tokens" not in columns:
        conn.execute(
            """
            ALTER TABLE agent_context_entries
            ADD COLUMN delta_compact_tokens INTEGER NULL
            """
        )
    _create_agent_context_usage_marker_index(conn)


def _create_agent_context_usage_marker_index(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_context_usage_markers_context_sequence
        ON agent_context_entries(context_id, sequence)
        WHERE usage_json IS NOT NULL
          AND delta_tokens IS NOT NULL
        """
    )


def _db_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    if row is None:
        return 0
    return int(row[0])


def _set_db_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {version}")


def _should_reset_db(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    with sqlite3.connect(db_path) as conn:
        current_version = _db_version(conn)
        if current_version in {7, SQLITE_RUNTIME_DB_VERSION}:
            return False
        table_count = _table_count(conn)
    return not (current_version == 0 and table_count == 0)


def _table_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        """
    ).fetchone()
    if row is None:
        return 0
    return int(row[0])


def _table_columns(conn: sqlite3.Connection, *, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def _delete_db_files(db_path: Path) -> None:
    for path in _db_files(db_path):
        if path.exists():
            path.unlink()


def _db_files(db_path: Path) -> tuple[Path, Path, Path]:
    return (
        db_path,
        Path(f"{db_path}-wal"),
        Path(f"{db_path}-shm"),
    )


def _create_runtime_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
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

        CREATE TABLE IF NOT EXISTS log_events (
          id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          sequence INTEGER NOT NULL,
          event_type TEXT NOT NULL,
          step_id TEXT,
          step_type TEXT,
          agent_sequence INTEGER,
          body_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(run_id, sequence),
          FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS external_receipts (
          dedup_key TEXT PRIMARY KEY,
          source_type TEXT NOT NULL,
          source_name TEXT NOT NULL,
          match_type TEXT NOT NULL,
          match_key TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS waits (
          id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          step_id TEXT NOT NULL,
          wait_type TEXT NOT NULL,
          source_type TEXT NOT NULL,
          source_name TEXT NOT NULL,
          match_type TEXT NOT NULL,
          match_key TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          expires_at TEXT,
          resolved_at TEXT,
          FOREIGN KEY(run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS external_events (
          id TEXT PRIMARY KEY,
          source_type TEXT NOT NULL,
          source_name TEXT NOT NULL,
          match_type TEXT NOT NULL,
          match_key TEXT NOT NULL,
          run_id TEXT,
          step_id TEXT,
          external_id TEXT,
          dedup_key TEXT,
          status TEXT NOT NULL,
          consumed_by_run_id TEXT,
          consumed_at TEXT,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(run_id) REFERENCES runs(id),
          FOREIGN KEY(consumed_by_run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS webhook_registrations (
          webhook TEXT PRIMARY KEY,
          secret TEXT NOT NULL,
          method TEXT NOT NULL DEFAULT 'POST',
          auth TEXT NOT NULL DEFAULT 'signed',
          payload_source TEXT NOT NULL DEFAULT 'body_json',
          enabled INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS agent_context_entries (
          id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          context_id TEXT NOT NULL,
          sequence INTEGER NOT NULL,
          entry_type TEXT NOT NULL,
          message_type TEXT NULL,
          window_start_sequence INTEGER NULL,
          delta_tokens INTEGER NULL,
          delta_compact_tokens INTEGER NULL,
          window_base INTEGER NULL,
          payload_json TEXT NOT NULL,
          usage_json TEXT NULL,
          source_step_id TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(run_id) REFERENCES runs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_runs_status_updated_at ON runs(status, updated_at);
        CREATE INDEX IF NOT EXISTS idx_log_events_run_sequence
          ON log_events(run_id, sequence);
        CREATE INDEX IF NOT EXISTS idx_log_events_run_type
          ON log_events(run_id, event_type);
        CREATE INDEX IF NOT EXISTS idx_log_events_agent_sequence
          ON log_events(run_id, agent_sequence);
        CREATE INDEX IF NOT EXISTS idx_external_receipts_source_match_created_at
          ON external_receipts(source_type, source_name, match_type, match_key, created_at);
        CREATE INDEX IF NOT EXISTS idx_waits_run_step_type_status
          ON waits(run_id, step_id, wait_type, status);
        CREATE INDEX IF NOT EXISTS idx_waits_source_match_type_status
          ON waits(source_type, source_name, match_type, match_key, wait_type, status);
        CREATE INDEX IF NOT EXISTS idx_external_events_source_run_step_created_at
          ON external_events(source_type, run_id, step_id, status, created_at);
        CREATE INDEX IF NOT EXISTS idx_external_events_source_match_created_at
          ON external_events(
            source_type,
            source_name,
            match_type,
            match_key,
            status,
            created_at
          );
        CREATE INDEX IF NOT EXISTS idx_agent_context_entries_context
          ON agent_context_entries(context_id, sequence);
        CREATE INDEX IF NOT EXISTS idx_agent_context_usage_markers_context_sequence
          ON agent_context_entries(context_id, sequence)
          WHERE usage_json IS NOT NULL
            AND delta_tokens IS NOT NULL;
        """
    )
