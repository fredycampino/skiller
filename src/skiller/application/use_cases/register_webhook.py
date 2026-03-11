from dataclasses import dataclass
from enum import Enum
import secrets

from skiller.application.ports.webhook_registry_port import WebhookRegistryPort


class RegisterWebhookStatus(str, Enum):
    REGISTERED = "REGISTERED"
    INVALID_WEBHOOK = "INVALID_WEBHOOK"
    ALREADY_REGISTERED = "ALREADY_REGISTERED"


@dataclass(frozen=True)
class RegisterWebhookResult:
    status: RegisterWebhookStatus
    webhook: str
    secret: str | None = None
    enabled: bool | None = None
    error: str | None = None


class RegisterWebhookUseCase:
    def __init__(self, registry: WebhookRegistryPort) -> None:
        self.registry = registry

    def execute(self, webhook: str) -> RegisterWebhookResult:
        normalized = webhook.strip()
        if not normalized:
            return RegisterWebhookResult(
                status=RegisterWebhookStatus.INVALID_WEBHOOK,
                webhook=webhook,
                error="webhook is required",
            )

        existing = self.registry.get_webhook_registration(normalized)
        if existing is not None:
            return RegisterWebhookResult(
                status=RegisterWebhookStatus.ALREADY_REGISTERED,
                webhook=normalized,
                error=f"Webhook '{normalized}' is already registered",
            )

        secret = secrets.token_urlsafe(32)
        self.registry.register_webhook(normalized, secret)
        return RegisterWebhookResult(
            status=RegisterWebhookStatus.REGISTERED,
            webhook=normalized,
            secret=secret,
            enabled=True,
        )
