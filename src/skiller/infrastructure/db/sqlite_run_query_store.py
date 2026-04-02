from typing import Any

from skiller.domain.run_list_item_model import RunListItem
from skiller.infrastructure.db.sqlite_repository import SqliteRepository


class SqliteRunQueryStore(SqliteRepository):
    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[RunListItem]:
        normalized_limit = max(1, limit)
        normalized_statuses = [
            status.strip().upper() for status in statuses or [] if status.strip()
        ]
        query = """
            SELECT
              runs.id,
              runs.skill_source,
              runs.skill_ref,
              runs.status,
              runs.current,
              runs.created_at,
              runs.updated_at,
              waits.wait_type,
              waits.webhook,
              waits.key
            FROM runs
            LEFT JOIN waits
              ON waits.run_id = runs.id
             AND waits.step_id = runs.current
             AND waits.status = 'ACTIVE'
        """
        params: list[Any] = []
        if normalized_statuses:
            placeholders = ", ".join("?" for _ in normalized_statuses)
            query += f" WHERE runs.status IN ({placeholders})"
            params.extend(normalized_statuses)
        query += """
            ORDER BY runs.updated_at DESC, runs.rowid DESC
            LIMIT ?
        """
        params.append(normalized_limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._build_item(row) for row in rows]

    def _build_item(self, row: Any) -> RunListItem:
        wait_type = self._normalize_wait_type(row["wait_type"])
        webhook = str(row["webhook"] or "").strip()
        key = str(row["key"] or "").strip()
        wait_detail: str | None = None
        if wait_type == "webhook" and webhook and key:
            wait_detail = f"{webhook}:{key}"
        return RunListItem(
            id=str(row["id"]),
            skill_source=str(row["skill_source"]),
            skill_ref=str(row["skill_ref"]),
            status=str(row["status"]),
            current=(str(row["current"]) if row["current"] is not None else None),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            wait_type=wait_type,
            wait_detail=wait_detail,
        )

    def _normalize_wait_type(self, raw_wait_type: object) -> str | None:
        value = str(raw_wait_type or "").strip().lower()
        if value == "input" or value == "wait_input":
            return "input"
        if value == "webhook" or value == "wait_webhook":
            return "webhook"
        return None
