from dataclasses import dataclass

from skiller.domain.event.webhook_registration_model import WebhookRegistration
from skiller.domain.event.webhook_registry_port import WebhookRegistryPort


@dataclass(frozen=True)
class ListWebhooksResult:
    webhooks: list[WebhookRegistration]


class ListWebhooksUseCase:
    def __init__(self, registry: WebhookRegistryPort) -> None:
        self.registry = registry

    def execute(self) -> ListWebhooksResult:
        return ListWebhooksResult(webhooks=self.registry.list_webhook_registrations())
