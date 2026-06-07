import json

from skiller.domain.run.run_model import Run
from skiller.domain.run.steering_model import SteeringItem, SteeringItemType
from skiller.domain.shared.steering_port import SteeringPort
from skiller.infrastructure.db.datasource.sqlite_connection_source import SqliteConnectionSource
from skiller.infrastructure.db.sqlite_run_mapper import build_run_from_row


class SqliteAgentSteeringStore(SqliteConnectionSource, SteeringPort):
    def get_run(self, run_id: str) -> Run | None:
        with self._connect() as conn:
            row = conn.execute(
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
