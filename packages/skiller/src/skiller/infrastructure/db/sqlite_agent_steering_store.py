import json
import sqlite3

from skiller.domain.run.run_model import Run
from skiller.domain.run.steering_model import SteeringItem, SteeringItemType
from skiller.domain.shared.steering_port import SteeringPort
from skiller.infrastructure.db.sqlite_repository import SqliteRepository
from skiller.infrastructure.db.sqlite_run_mapper import build_run_from_row


class SqliteAgentSteeringStore(SqliteRepository, SteeringPort):
    def get_run(self, run_id: str) -> Run | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                  id,
                  skill_source,
                  skill_ref,
                  skill_snapshot_json,
                  status,
                  current,
                  inputs_json,
                  step_executions_json,
                  steering_queue_json,
                  cancel_reason,
                  created_at,
                  updated_at
                FROM runs WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return build_run_from_row(row)

    def append(self, run_id: str, item: SteeringItem) -> None:
        run = self._get_run_or_raise(run_id)
        if item in run.context.steering_queue:
            return
        run.context.steering_queue.append(item)
        self._update_steering_queue(run_id, run.context.steering_queue)

    def pop(self, run_id: str, item_type: SteeringItemType) -> list[SteeringItem]:
        run = self._get_run_or_raise(run_id)
        removed: list[SteeringItem] = []
        remaining: list[SteeringItem] = []
        for item in run.context.steering_queue:
            if not isinstance(item, item_type):
                remaining.append(item)
                continue
            removed.append(item)

        if len(remaining) == len(run.context.steering_queue):
            return []

        self._update_steering_queue(run_id, remaining)
        return removed

    def _get_run_or_raise(self, run_id: str) -> Run:
        run = self.get_run(run_id)
        if run is None:
            raise ValueError(f"Run '{run_id}' not found")
        return run

    def _update_steering_queue(self, run_id: str, queue: list[SteeringItem]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET steering_queue_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps([item.to_dict() for item in queue]), run_id),
            )


def ensure_runs_steering_queue_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(runs)").fetchall()
    column_names = {str(row["name"]) for row in rows}
    if "steering_queue_json" in column_names:
        return
    conn.execute("ALTER TABLE runs ADD COLUMN steering_queue_json TEXT NOT NULL DEFAULT '[]'")
    if "steering_messages_json" in column_names:
        conn.execute(
            """
            UPDATE runs
            SET steering_queue_json = steering_messages_json
            WHERE steering_queue_json = '[]'
            """
        )
