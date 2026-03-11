from dataclasses import dataclass
from enum import Enum

from skiller.application.ports.webhook_registry_port import WebhookRegistryPort


class RemoveWebhookStatus(str, Enum):
    REMOVED = "REMOVED"
    INVALID_WEBHOOK = "INVALID_WEBHOOK"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class RemoveWebhookResult:
    status: RemoveWebhookStatus
    webhook: str
    error: str | None = None


class RemoveWebhookUseCase:
    def __init__(self, registry: WebhookRegistryPort) -> None:
        self.registry = registry

    def execute(self, webhook: str) -> RemoveWebhookResult:
        normalized = webhook.strip()
        if not normalized:
            return RemoveWebhookResult(
                status=RemoveWebhookStatus.INVALID_WEBHOOK,
                webhook=webhook,
                error="webhook is required",
            )

        removed = self.registry.remove_webhook(normalized)
        if not removed:
            return RemoveWebhookResult(
                status=RemoveWebhookStatus.NOT_FOUND,
                webhook=normalized,
                error=f"Webhook '{normalized}' is not registered",
            )

        return RemoveWebhookResult(status=RemoveWebhookStatus.REMOVED, webhook=normalized)
