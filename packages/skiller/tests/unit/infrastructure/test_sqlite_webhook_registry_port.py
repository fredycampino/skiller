import pytest

from skiller.domain.event.webhook_registration_model import (
    WebhookAuth,
    WebhookMethod,
    WebhookPayloadSource,
    WebhookRegistration,
    WebhookSecretUpdate,
)
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap
from skiller.infrastructure.db.sqlite_webhook_registry_port import SqliteWebhookRegistryPort

pytestmark = pytest.mark.unit


def test_sqlite_webhook_registry_port_lists_registered_webhooks(tmp_path) -> None:
    db_path = tmp_path / "webhooks.db"
    registry = SqliteWebhookRegistryPort(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()

    registry.register_webhook(
        WebhookRegistration(
            webhook="github-ci",
            secret="secret-1",
            method=WebhookMethod.POST,
            auth=WebhookAuth.SIGNED,
            payload_source=WebhookPayloadSource.BODY_JSON,
            token_header=None,
            enabled=True,
        )
    )
    registry.register_webhook(
        WebhookRegistration(
            webhook="market-signal",
            secret="secret-2",
            method=WebhookMethod.POST,
            auth=WebhookAuth.SIGNED,
            payload_source=WebhookPayloadSource.BODY_JSON,
            token_header=None,
            enabled=True,
        )
    )

    webhooks = registry.list_webhook_registrations()

    assert sorted(item.webhook for item in webhooks) == ["github-ci", "market-signal"]
    assert all(item.method.value == "POST" for item in webhooks)
    assert all(item.auth.value == "signed" for item in webhooks)
    assert all(item.payload_source.value == "body_json" for item in webhooks)
    assert all(item.token_header is None for item in webhooks)
    assert all(item.created_at is not None for item in webhooks)


def test_sqlite_webhook_registry_port_updates_existing_secret_only(tmp_path) -> None:
    db_path = tmp_path / "webhook-secret.db"
    registry = SqliteWebhookRegistryPort(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    registry.register_webhook(
        WebhookRegistration(
            webhook="telegram",
            secret="old-secret",
            method=WebhookMethod.POST,
            auth=WebhookAuth.TOKEN,
            payload_source=WebhookPayloadSource.BODY_JSON,
            token_header="X-Telegram-Bot-Api-Secret-Token",
            enabled=True,
        )
    )

    assert registry.update_webhook_secret(
        WebhookSecretUpdate(webhook="telegram", secret="new-secret")
    )
    assert not registry.update_webhook_secret(
        WebhookSecretUpdate(webhook="missing", secret="other-secret")
    )

    registration = registry.get_webhook_registration("telegram")
    assert registration is not None
    assert registration.secret == "new-secret"
    assert registration.auth == WebhookAuth.TOKEN
    assert registration.token_header == "X-Telegram-Bot-Api-Secret-Token"
