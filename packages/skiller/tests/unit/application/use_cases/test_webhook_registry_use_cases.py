from skiller.application.use_cases.query.list_webhooks import ListWebhooksUseCase
from skiller.application.use_cases.webhook.register_webhook import (
    RegisterWebhookInput,
    RegisterWebhookStatus,
    RegisterWebhookUseCase,
)
from skiller.application.use_cases.webhook.remove_webhook import (
    RemoveWebhookStatus,
    RemoveWebhookUseCase,
)
from skiller.application.use_cases.webhook.update_webhook_secret import (
    UpdateWebhookSecretInput,
    UpdateWebhookSecretStatus,
    UpdateWebhookSecretUseCase,
)
from skiller.domain.event.webhook_registration_model import (
    WebhookAuth,
    WebhookMethod,
    WebhookPayloadSource,
    WebhookRegistration,
    WebhookSecretUpdate,
)


class _FakeRegistry:
    def __init__(self) -> None:
        self.records: dict[str, WebhookRegistration] = {}

    def register_webhook(self, registration: WebhookRegistration) -> None:
        self.records[registration.webhook] = registration

    def get_webhook_registration(self, webhook: str) -> WebhookRegistration | None:
        return self.records.get(webhook)

    def update_webhook_secret(self, update: WebhookSecretUpdate) -> bool:
        registration = self.records.get(update.webhook)
        if registration is None:
            return False
        self.records[update.webhook] = WebhookRegistration(
            webhook=registration.webhook,
            secret=update.secret,
            method=registration.method,
            auth=registration.auth,
            payload_source=registration.payload_source,
            token_header=registration.token_header,
            enabled=registration.enabled,
            created_at=registration.created_at,
        )
        return True

    def list_webhook_registrations(self) -> list[WebhookRegistration]:
        return list(self.records.values())

    def remove_webhook(self, webhook: str) -> bool:
        return self.records.pop(webhook, None) is not None


class _FakeEnvironmentSecretPort:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}
        self.names: list[str] = []

    def get_secret(self, name: str) -> str | None:
        self.names.append(name)
        return self.values.get(name)


def test_register_webhook_creates_secret_once() -> None:
    registry = _FakeRegistry()

    result = RegisterWebhookUseCase(registry).execute(
        RegisterWebhookInput(
            webhook="github-ci",
            method=WebhookMethod.POST,
            auth=WebhookAuth.SIGNED,
            payload_source=WebhookPayloadSource.BODY_JSON,
            token_header=None,
        )
    )

    assert result.status == RegisterWebhookStatus.REGISTERED
    assert result.webhook == "github-ci"
    assert result.method == WebhookMethod.POST
    assert result.auth == WebhookAuth.SIGNED
    assert result.payload_source == WebhookPayloadSource.BODY_JSON
    assert result.secret
    assert registry.records["github-ci"].secret == result.secret


def test_register_webhook_accepts_get_query_without_signature() -> None:
    registry = _FakeRegistry()

    result = RegisterWebhookUseCase(registry).execute(
        RegisterWebhookInput(
            webhook="example-auth",
            method=WebhookMethod.GET,
            auth=WebhookAuth.NONE,
            payload_source=WebhookPayloadSource.QUERY,
            token_header=None,
        )
    )

    assert result.status == RegisterWebhookStatus.REGISTERED
    assert result.method == WebhookMethod.GET
    assert result.auth == WebhookAuth.NONE
    assert result.payload_source == WebhookPayloadSource.QUERY
    assert registry.records["example-auth"].method == WebhookMethod.GET
    assert registry.records["example-auth"].auth == WebhookAuth.NONE
    assert registry.records["example-auth"].payload_source == WebhookPayloadSource.QUERY


def test_register_webhook_rejects_duplicate() -> None:
    registry = _FakeRegistry()
    registry.register_webhook(
        WebhookRegistration(
            webhook="github-ci",
            secret="secret",
            method=WebhookMethod.POST,
            auth=WebhookAuth.SIGNED,
            payload_source=WebhookPayloadSource.BODY_JSON,
            token_header=None,
            enabled=True,
        )
    )

    result = RegisterWebhookUseCase(registry).execute(
        RegisterWebhookInput(
            webhook="github-ci",
            method=WebhookMethod.POST,
            auth=WebhookAuth.SIGNED,
            payload_source=WebhookPayloadSource.BODY_JSON,
            token_header=None,
        )
    )

    assert result.status == RegisterWebhookStatus.ALREADY_REGISTERED
    assert result.error == "Webhook 'github-ci' is already registered"


def test_remove_webhook_deletes_registration() -> None:
    registry = _FakeRegistry()
    registry.register_webhook(
        WebhookRegistration(
            webhook="github-ci",
            secret="secret",
            method=WebhookMethod.POST,
            auth=WebhookAuth.SIGNED,
            payload_source=WebhookPayloadSource.BODY_JSON,
            token_header=None,
            enabled=True,
        )
    )

    result = RemoveWebhookUseCase(registry).execute("github-ci")

    assert result.status == RemoveWebhookStatus.REMOVED
    assert "github-ci" not in registry.records


def test_remove_webhook_returns_not_found() -> None:
    registry = _FakeRegistry()

    result = RemoveWebhookUseCase(registry).execute("github-ci")

    assert result.status == RemoveWebhookStatus.NOT_FOUND
    assert result.error == "Webhook 'github-ci' is not registered"


def test_update_webhook_secret_changes_only_the_secret() -> None:
    registry = _FakeRegistry()
    environment_secret = _FakeEnvironmentSecretPort({"TELEGRAM_SECRET": "new-secret"})
    registration = WebhookRegistration(
        webhook="telegram",
        secret="old-secret",
        method=WebhookMethod.POST,
        auth=WebhookAuth.TOKEN,
        payload_source=WebhookPayloadSource.BODY_JSON,
        token_header="X-Telegram-Bot-Api-Secret-Token",
        enabled=True,
        created_at="2026-09-11 10:00:00",
    )
    registry.register_webhook(registration)

    result = UpdateWebhookSecretUseCase(registry, environment_secret).execute(
        UpdateWebhookSecretInput(webhook="telegram", secret_env_name="TELEGRAM_SECRET")
    )

    updated = registry.records["telegram"]
    assert result.status == UpdateWebhookSecretStatus.UPDATED
    assert environment_secret.names == ["TELEGRAM_SECRET"]
    assert updated.secret == "new-secret"
    assert updated.method == registration.method
    assert updated.auth == registration.auth
    assert updated.token_header == registration.token_header
    assert updated.created_at == registration.created_at


def test_update_webhook_secret_returns_not_found() -> None:
    result = UpdateWebhookSecretUseCase(
        _FakeRegistry(),
        _FakeEnvironmentSecretPort({"WEBHOOK_SECRET": "new-secret"}),
    ).execute(
        UpdateWebhookSecretInput(webhook="missing", secret_env_name="WEBHOOK_SECRET")
    )

    assert result.status == UpdateWebhookSecretStatus.NOT_FOUND
    assert result.error == "Webhook 'missing' is not registered"


def test_update_webhook_secret_rejects_a_missing_environment_value() -> None:
    environment_secret = _FakeEnvironmentSecretPort()

    result = UpdateWebhookSecretUseCase(_FakeRegistry(), environment_secret).execute(
        UpdateWebhookSecretInput(webhook="telegram", secret_env_name="MISSING_SECRET")
    )

    assert result.status == UpdateWebhookSecretStatus.INVALID_SECRET
    assert environment_secret.names == ["MISSING_SECRET"]


def test_list_webhooks_returns_registered_channels() -> None:
    registry = _FakeRegistry()
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

    result = ListWebhooksUseCase(registry).execute()

    assert [item.webhook for item in result.webhooks] == ["github-ci", "market-signal"]


def test_register_webhook_persists_token_header() -> None:
    registry = _FakeRegistry()

    result = RegisterWebhookUseCase(registry).execute(
        RegisterWebhookInput(
            webhook="provider-events",
            method=WebhookMethod.POST,
            auth=WebhookAuth.TOKEN,
            payload_source=WebhookPayloadSource.BODY_JSON,
            token_header="X-Webhook-Token",
        )
    )

    assert result.auth == WebhookAuth.TOKEN
    assert result.token_header == "X-Webhook-Token"
    assert registry.records["provider-events"].token_header == "X-Webhook-Token"
