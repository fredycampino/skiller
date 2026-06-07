import sqlite3

from skiller.infrastructure.db.datasource.sqlite_connection_source import SqliteConnectionSource


class SqliteRunDatasource(SqliteConnectionSource):
    def create_run_row(
        self,
        *,
        run_id: str,
        source: str,
        ref: str,
        snapshot_json: str,
        status: str,
        inputs_json: str,
        step_executions_json: str,
        steering_queue_json: str,
    ) -> str:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                  id,
                  source,
                  ref,
                  snapshot_json,
                  status,
                  current,
                  inputs_json,
                  step_executions_json,
                  agents_json,
                  steering_queue_json
                )
                VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source,
                    ref,
                    snapshot_json,
                    status,
                    inputs_json,
                    step_executions_json,
                    "{}",
                    steering_queue_json,
                ),
            )
        return run_id

    def update_run_row(
        self,
        *,
        run_id: str,
        status: str | None = None,
        current: str | None = None,
        step_executions_json: str | None = None,
        cancel_reason: str | None = None,
        finished: bool = False,
        expire_active_waits: bool = False,
    ) -> None:
        updates: list[str] = []
        params: list[object] = []

        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if current is not None:
            updates.append("current = ?")
            params.append(current)
        if step_executions_json is not None:
            updates.append("step_executions_json = ?")
            params.append(step_executions_json)
            updates.append("cancel_reason = ?")
            params.append(cancel_reason)
        if finished:
            updates.append("finished_at = CURRENT_TIMESTAMP")

        if not updates:
            return

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(run_id)

        query = f"UPDATE runs SET {', '.join(updates)} WHERE id = ?"
        with self._connect() as conn:
            conn.execute(query, params)
            if expire_active_waits:
                conn.execute(
                    """
                    UPDATE waits
                    SET status = 'EXPIRED', resolved_at = CURRENT_TIMESTAMP
                    WHERE run_id = ? AND status = 'ACTIVE'
                    """,
                    (run_id,),
                )

    def get_run_row(self, run_id: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                  id,
                  source,
                  ref,
                  snapshot_json,
                  status,
                  current,
                  inputs_json,
                  step_executions_json,
                  agents_json,
                  steering_queue_json,
                  cancel_reason,
                  created_at,
                  updated_at
                FROM runs WHERE id = ?
                """,
                (run_id,),
            ).fetchone()

    def get_status_row(self, run_id: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT id, status
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()

    def get_snapshot_sync_state_row(self, run_id: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT id, source, ref, current, snapshot_json
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()

    def update_snapshot_json(self, run_id: str, snapshot_json: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET snapshot_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (snapshot_json, run_id),
            )

    def cleanup_run(self, run_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                return False

            _delete_run_related_rows(conn, run_id)
            conn.execute(
                """
                DELETE FROM log_events
                WHERE run_id = ?
                  AND event_type NOT IN ('RUN_CREATE', 'RUN_FINISHED')
                """,
                (run_id,),
            )
            conn.execute(
                """
                UPDATE runs
                SET
                  inputs_json = '{}',
                  step_executions_json = '{}',
                  steering_queue_json = '[]',
                  cancel_reason = NULL,
                  updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (run_id,),
            )
        return True

    def delete_run(self, run_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                return False

            _delete_run_related_rows(conn, run_id)
            conn.execute("DELETE FROM log_events WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        return True


def _delete_run_related_rows(conn: sqlite3.Connection, run_id: str) -> None:
    agent_context_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'agent_context_entries'"
    ).fetchone()
    if agent_context_table is not None:
        conn.execute("DELETE FROM agent_context_entries WHERE run_id = ?", (run_id,))

    conn.execute(
        """
        DELETE FROM external_receipts
        WHERE dedup_key IN (
          SELECT dedup_key
          FROM external_events
          WHERE (run_id = ? OR consumed_by_run_id = ?)
            AND dedup_key IS NOT NULL
        )
        """,
        (run_id, run_id),
    )
    conn.execute(
        """
        DELETE FROM external_events
        WHERE run_id = ? OR consumed_by_run_id = ?
        """,
        (run_id, run_id),
    )
    conn.execute("DELETE FROM waits WHERE run_id = ?", (run_id,))
