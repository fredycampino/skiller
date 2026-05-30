import sqlite3
from pathlib import Path

from skiller.domain.run.runtime_bootstrap_port import RuntimeBootstrapPort
from skiller.infrastructure.db.sqlite_agent_context_datasource import (
    ensure_agent_context_schema,
)
from skiller.infrastructure.db.sqlite_repository import SqliteRepository

SQLITE_RUNTIME_DB_VERSION = 3


class SqliteRuntimeBootstrap(SqliteRepository, RuntimeBootstrapPort):
    def init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            apply_db_updates(conn)
            _create_runtime_schema(conn)


def apply_db_updates(conn: sqlite3.Connection) -> None:
    current_version = _db_version(conn)
    if current_version == SQLITE_RUNTIME_DB_VERSION:
        return
    _update_db_from(conn, current_version)
    _set_db_version(conn, SQLITE_RUNTIME_DB_VERSION)


def _db_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    if row is None:
        return 0
    return int(row[0])


def _set_db_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {version}")


def _update_db_from(conn: sqlite3.Connection, version: int) -> None:
    _ = version
    conn.executescript(
        """
        PRAGMA foreign_keys = OFF;
        DROP TABLE IF EXISTS agent_context_entries;
        DROP TABLE IF EXISTS webhook_registrations;
        DROP TABLE IF EXISTS waits;
        DROP TABLE IF EXISTS external_events;
        DROP TABLE IF EXISTS external_receipts;
        DROP TABLE IF EXISTS log_events;
        DROP TABLE IF EXISTS runs;
        PRAGMA foreign_keys = ON;
        """
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
        """
    )
    ensure_agent_context_schema(conn)
