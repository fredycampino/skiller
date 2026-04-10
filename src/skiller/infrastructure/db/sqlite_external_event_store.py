import json
import sqlite3
import uuid
from typing import Any

from skiller.domain.match_type import MatchType
from skiller.domain.source_type import SourceType
from skiller.infrastructure.db.sqlite_repository import SqliteRepository


class SqliteExternalEventStore(SqliteRepository):
    PENDING_STATUS = "pending"
    CONSUMED_STATUS = "consumed"

    def create_external_event(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        payload: dict[str, Any],
        run_id: str | None = None,
        step_id: str | None = None,
        external_id: str | None = None,
        dedup_key: str | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO external_events (
                  id,
                  source_type,
                  source_name,
                  match_type,
                  match_key,
                  run_id,
                  step_id,
                  external_id,
                  dedup_key,
                  status,
                  payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    source_type.value,
                    source_name,
                    match_type.value,
                    match_key,
                    run_id,
                    step_id,
                    external_id,
                    dedup_key,
                    self.PENDING_STATUS,
                    json.dumps(payload),
                ),
            )
        return event_id

    def get_latest_external_event(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        run_id: str | None = None,
        step_id: str | None = None,
        since_created_at: str | None = None,
    ) -> dict[str, Any] | None:
        query = """
            SELECT
                id,
                source_type,
                source_name,
                match_type,
                match_key,
                run_id,
                step_id,
                external_id,
                dedup_key,
                status,
                consumed_by_run_id,
                consumed_at,
                payload_json,
                created_at
            FROM external_events
            WHERE source_type = ? AND source_name = ? AND match_type = ?
              AND status = ?
        """
        params: list[Any] = [
            source_type.value,
            source_name,
            match_type.value,
            self.PENDING_STATUS,
        ]
        if match_type == MatchType.CHANNEL_KEY and match_key == "all":
            pass
        else:
            query += " AND match_key = ?"
            params.append(match_key)
        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        if step_id is not None:
            query += " AND step_id = ?"
            params.append(step_id)
        if since_created_at:
            query += " AND created_at >= ?"
            params.append(since_created_at)

        query += " ORDER BY created_at ASC, rowid ASC LIMIT 1"

        with self._connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
        if row is None:
            return None
        return self._build_external_event_payload(row)

    def consume_external_event(
        self,
        event_id: str,
        *,
        run_id: str,
    ) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE external_events
                SET
                  status = ?,
                  consumed_by_run_id = ?,
                  consumed_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = ?
                """,
                (
                    self.CONSUMED_STATUS,
                    run_id,
                    event_id,
                    self.PENDING_STATUS,
                ),
            )
        return cursor.rowcount > 0

    def register_external_receipt(
        self,
        dedup_key: str,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        payload: dict[str, Any],
    ) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO external_receipts (
                      dedup_key,
                      source_type,
                      source_name,
                      match_type,
                      match_key,
                      payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dedup_key,
                        source_type.value,
                        source_name,
                        match_type.value,
                        match_key,
                        json.dumps(payload),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def _build_external_event_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            payload = {}

        return {
            "id": row["id"],
            "source_type": row["source_type"],
            "source_name": row["source_name"],
            "match_type": row["match_type"],
            "match_key": row["match_key"],
            "run_id": row["run_id"],
            "step_id": row["step_id"],
            "external_id": row["external_id"],
            "dedup_key": row["dedup_key"],
            "status": row["status"],
            "consumed_by_run_id": row["consumed_by_run_id"],
            "consumed_at": row["consumed_at"],
            "payload": payload,
            "created_at": row["created_at"],
        }
