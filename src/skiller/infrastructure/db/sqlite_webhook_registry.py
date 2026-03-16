from typing import Any

from skiller.infrastructure.db.sqlite_repository import SqliteRepository


class SqliteWebhookRegistry(SqliteRepository):
    def register_webhook(self, webhook: str, secret: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO webhook_registrations (webhook, secret, enabled)
                VALUES (?, ?, 1)
                """,
                (webhook, secret),
            )

    def get_webhook_registration(self, webhook: str) -> dict[str, Any] | None:
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

    def remove_webhook(self, webhook: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM webhook_registrations WHERE webhook = ?", (webhook,))
        return cursor.rowcount > 0
