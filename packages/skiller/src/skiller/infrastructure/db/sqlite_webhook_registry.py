from typing import Any

from skiller.domain.event.webhook_registration_model import (
    WebhookAuth,
    WebhookMethod,
    WebhookPayloadSource,
)
from skiller.domain.event.webhook_registry_port import WebhookRegistryPort
from skiller.infrastructure.db.datasource.sqlite_connection_source import SqliteConnectionSource


class SqliteWebhookRegistry(SqliteConnectionSource, WebhookRegistryPort):
    def register_webhook(
        self,
        webhook: str,
        secret: str,
        *,
        method: WebhookMethod,
        auth: WebhookAuth,
        payload_source: WebhookPayloadSource,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO webhook_registrations (
                  webhook,
                  secret,
                  method,
                  auth,
                  payload_source,
                  enabled
                )
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    webhook,
                    secret,
                    method.value,
                    auth.value,
                    payload_source.value,
                ),
            )

    def get_webhook_registration(self, webhook: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT webhook, secret, method, auth, payload_source, enabled, created_at
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
            "method": row["method"],
            "auth": row["auth"],
            "payload_source": row["payload_source"],
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
        }

    def list_webhook_registrations(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT webhook, secret, method, auth, payload_source, enabled, created_at
                FROM webhook_registrations
                ORDER BY created_at DESC, webhook ASC
                """
            ).fetchall()
        return [
            {
                "webhook": row["webhook"],
                "secret": row["secret"],
                "method": row["method"],
                "auth": row["auth"],
                "payload_source": row["payload_source"],
                "enabled": bool(row["enabled"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def remove_webhook(self, webhook: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM webhook_registrations WHERE webhook = ?", (webhook,))
        return cursor.rowcount > 0
