from typing import Protocol

from skiller.domain.event.webhook_registration_model import (
    WebhookAuth,
    WebhookMethod,
    WebhookPayloadSource,
)


class WebhookRegistryPort(Protocol):
    def register_webhook(
        self,
        webhook: str,
        secret: str,
        *,
        method: WebhookMethod,
        auth: WebhookAuth,
        payload_source: WebhookPayloadSource,
    ) -> None: ...

    def get_webhook_registration(self, webhook: str) -> dict[str, object] | None: ...

    def list_webhook_registrations(self) -> list[dict[str, object]]: ...

    def remove_webhook(self, webhook: str) -> bool: ...
