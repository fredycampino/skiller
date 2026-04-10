import sqlite3
import uuid
from typing import Any

from skiller.domain.match_type import MatchType
from skiller.domain.source_type import SourceType
from skiller.domain.wait_type import WaitType
from skiller.infrastructure.db.sqlite_repository import SqliteRepository


class SqliteWaitStore(SqliteRepository):
    def create_wait(
        self,
        run_id: str,
        *,
        step_id: str,
        wait_type: WaitType,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        expires_at: str | None = None,
    ) -> str:
        wait_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO waits (
                  id,
                  run_id,
                  step_id,
                  wait_type,
                  source_type,
                  source_name,
                  match_type,
                  match_key,
                  status,
                  expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
                """,
                (
                    wait_id,
                    run_id,
                    step_id,
                    wait_type.value,
                    source_type.value,
                    source_name,
                    match_type.value,
                    match_key,
                    expires_at,
                ),
            )
        return wait_id

    def resolve_wait(self, wait_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE waits
                SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (wait_id,),
            )

    def get_active_wait(
        self,
        run_id: str,
        step_id: str,
        *,
        wait_type: WaitType,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                  id,
                  run_id,
                  step_id,
                  wait_type,
                  source_type,
                  source_name,
                  match_type,
                  match_key,
                  status,
                  created_at,
                  resolved_at,
                  expires_at
                FROM waits
                WHERE run_id = ? AND step_id = ? AND wait_type = ? AND status = 'ACTIVE'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (run_id, step_id, wait_type.value),
            ).fetchone()
        if row is None:
            return None
        return self._build_wait_payload(row)

    def find_matching_waits(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if match_type == MatchType.CHANNEL_KEY:
                rows = conn.execute(
                    """
                    SELECT
                      id,
                      run_id,
                      step_id,
                      wait_type,
                      source_type,
                      source_name,
                      match_type,
                      match_key,
                      status,
                      created_at,
                      resolved_at,
                      expires_at
                    FROM waits
                    WHERE source_type = ?
                      AND source_name = ?
                      AND match_type = ?
                      AND (match_key = ? OR match_key = 'all')
                      AND status = 'ACTIVE'
                    ORDER BY created_at ASC
                    """,
                    (
                        source_type.value,
                        source_name,
                        match_type.value,
                        match_key,
                    ),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                      id,
                      run_id,
                      step_id,
                      wait_type,
                      source_type,
                      source_name,
                      match_type,
                      match_key,
                      status,
                      created_at,
                      resolved_at,
                      expires_at
                    FROM waits
                    WHERE source_type = ?
                      AND source_name = ?
                      AND match_type = ?
                      AND match_key = ?
                      AND status = 'ACTIVE'
                    ORDER BY created_at ASC
                    """,
                    (
                        source_type.value,
                        source_name,
                        match_type.value,
                        match_key,
                    ),
                ).fetchall()

        return [self._build_wait_payload(row) for row in rows]

    def expire_active_waits_for_run(self, run_id: str) -> int:
        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE waits
                SET status = 'EXPIRED', resolved_at = CURRENT_TIMESTAMP
                WHERE run_id = ? AND status = 'ACTIVE'
                """,
                (run_id,),
            )
            return result.rowcount

    def _build_wait_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "step_id": row["step_id"],
            "wait_type": row["wait_type"],
            "source_type": row["source_type"],
            "source_name": row["source_name"],
            "match_type": row["match_type"],
            "match_key": row["match_key"],
            "status": row["status"],
            "created_at": row["created_at"],
            "resolved_at": row["resolved_at"],
            "expires_at": row["expires_at"],
        }
