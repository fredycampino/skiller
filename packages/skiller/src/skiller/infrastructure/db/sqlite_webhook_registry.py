import sqlite3

from skiller.domain.event.webhook_registration_model import (
    WebhookAuth,
    WebhookMethod,
    WebhookPayloadSource,
    WebhookRegistration,
)
from skiller.domain.event.webhook_registry_port import WebhookRegistryPort
from skiller.infrastructure.db.datasource.sqlite_connection_source import SqliteConnectionSource


class SqliteWebhookRegistry(SqliteConnectionSource, WebhookRegistryPort):
    def register_webhook(self, registration: WebhookRegistration) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO webhook_registrations (
                  webhook, secret, method, auth, payload_source, token_header, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    registration.webhook,
                    registration.secret,
                    registration.method.value,
                    registration.auth.value,
                    registration.payload_source.value,
                    registration.token_header,
                    registration.enabled,
                ),
            )

    def get_webhook_registration(self, webhook: str) -> WebhookRegistration | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT webhook, secret, method, auth, payload_source, token_header,
                       enabled, created_at
                FROM webhook_registrations WHERE webhook = ?
                """,
                (webhook,),
            ).fetchone()
        return _to_registration(row) if row is not None else None

    def list_webhook_registrations(self) -> list[WebhookRegistration]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT webhook, secret, method, auth, payload_source, token_header,
                       enabled, created_at
                FROM webhook_registrations ORDER BY created_at DESC, webhook ASC
                """
            ).fetchall()
        return [_to_registration(row) for row in rows]

    def remove_webhook(self, webhook: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM webhook_registrations WHERE webhook = ?", (webhook,))
        return cursor.rowcount > 0


def _to_registration(row: sqlite3.Row) -> WebhookRegistration:
    return WebhookRegistration(
        webhook=str(row["webhook"]),
        secret=str(row["secret"]),
        method=WebhookMethod(str(row["method"])),
        auth=WebhookAuth(str(row["auth"])),
        payload_source=WebhookPayloadSource(str(row["payload_source"])),
        token_header=row["token_header"],
        enabled=bool(row["enabled"]),
        created_at=str(row["created_at"]),
    )
