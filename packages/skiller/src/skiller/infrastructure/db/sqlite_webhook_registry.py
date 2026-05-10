from pathlib import Path
from typing import Any

from skiller.infrastructure.db.sqlite_repository import SqliteRepository


class SqliteWebhookRegistry(SqliteRepository):
    def init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_registrations (
                  webhook TEXT PRIMARY KEY,
                  secret TEXT NOT NULL,
                  enabled INTEGER NOT NULL DEFAULT 1,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def register_webhook(self, webhook: str, secret: str) -> None:
        self.init_db()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO webhook_registrations (webhook, secret, enabled)
                VALUES (?, ?, 1)
                """,
                (webhook, secret),
            )

    def get_webhook_registration(self, webhook: str) -> dict[str, Any] | None:
        self.init_db()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT webhook, secret, enabled, created_at
                FROM webhook_registrations
                WHERE webhook = ?
                """,
                (webhook,),
            ).fetchone()
        if row is None:
            return None
        return {
            "webhook": row["webhook"],
            "secret": row["secret"],
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
        }

    def list_webhook_registrations(self) -> list[dict[str, Any]]:
        self.init_db()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT webhook, secret, enabled, created_at
                FROM webhook_registrations
                ORDER BY created_at DESC, webhook ASC
                """
            ).fetchall()
        return [
            {
                "webhook": row["webhook"],
                "secret": row["secret"],
                "enabled": bool(row["enabled"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def remove_webhook(self, webhook: str) -> bool:
        self.init_db()
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM webhook_registrations WHERE webhook = ?", (webhook,))
        return cursor.rowcount > 0
