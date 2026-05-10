from skiller.application.use_cases.query.list_webhooks import ListWebhooksUseCase
from skiller.application.use_cases.webhook.register_webhook import (
    RegisterWebhookStatus,
    RegisterWebhookUseCase,
)
from skiller.application.use_cases.webhook.remove_webhook import (
    RemoveWebhookStatus,
    RemoveWebhookUseCase,
)


class _FakeRegistry:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, object]] = {}

    def register_webhook(self, webhook: str, secret: str) -> None:
        self.records[webhook] = {"webhook": webhook, "secret": secret, "enabled": True}

    def get_webhook_registration(self, webhook: str) -> dict[str, object] | None:
        return self.records.get(webhook)

    def list_webhook_registrations(self) -> list[dict[str, object]]:
        return list(self.records.values())

    def remove_webhook(self, webhook: str) -> bool:
        return self.records.pop(webhook, None) is not None


def test_register_webhook_creates_secret_once() -> None:
    registry = _FakeRegistry()

    result = RegisterWebhookUseCase(registry).execute("github-ci")

    assert result.status == RegisterWebhookStatus.REGISTERED
    assert result.webhook == "github-ci"
    assert result.secret
    assert registry.records["github-ci"]["secret"] == result.secret


def test_register_webhook_rejects_duplicate() -> None:
    registry = _FakeRegistry()
    registry.register_webhook("github-ci", "secret")

    result = RegisterWebhookUseCase(registry).execute("github-ci")

    assert result.status == RegisterWebhookStatus.ALREADY_REGISTERED
    assert result.error == "Webhook 'github-ci' is already registered"


def test_remove_webhook_deletes_registration() -> None:
    registry = _FakeRegistry()
    registry.register_webhook("github-ci", "secret")

    result = RemoveWebhookUseCase(registry).execute("github-ci")

    assert result.status == RemoveWebhookStatus.REMOVED
    assert "github-ci" not in registry.records


def test_remove_webhook_returns_not_found() -> None:
    registry = _FakeRegistry()

    result = RemoveWebhookUseCase(registry).execute("github-ci")

    assert result.status == RemoveWebhookStatus.NOT_FOUND
    assert result.error == "Webhook 'github-ci' is not registered"


def test_list_webhooks_returns_registered_channels() -> None:
    registry = _FakeRegistry()
    registry.register_webhook("github-ci", "secret-1")
    registry.register_webhook("market-signal", "secret-2")

    result = ListWebhooksUseCase(registry).execute()

    assert [item["webhook"] for item in result.webhooks] == ["github-ci", "market-signal"]
