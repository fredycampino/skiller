from typing import Protocol


class WebhookRegistryPort(Protocol):
    def register_webhook(self, webhook: str, secret: str) -> None:
        ...

    def get_webhook_registration(self, webhook: str) -> dict[str, object] | None:
        ...

    def remove_webhook(self, webhook: str) -> bool:
        ...
