from dataclasses import dataclass
from enum import Enum

from skiller.domain.config.environment_secret_port import EnvironmentSecretPort
from skiller.domain.event.webhook_registration_model import WebhookSecretUpdate
from skiller.domain.event.webhook_registry_port import WebhookRegistryPort


@dataclass(frozen=True)
class UpdateWebhookSecretInput:
    webhook: str
    secret_env_name: str


class UpdateWebhookSecretStatus(str, Enum):
    UPDATED = "UPDATED"
    INVALID_WEBHOOK = "INVALID_WEBHOOK"
    INVALID_SECRET = "INVALID_SECRET"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class UpdateWebhookSecretResult:
    status: UpdateWebhookSecretStatus
    webhook: str
    error: str | None = None


class UpdateWebhookSecretUseCase:
    def __init__(
        self,
        registry: WebhookRegistryPort,
        environment_secret: EnvironmentSecretPort,
    ) -> None:
        self.registry = registry
        self.environment_secret = environment_secret

    def execute(self, request: UpdateWebhookSecretInput) -> UpdateWebhookSecretResult:
        secret = self.environment_secret.get_secret(request.secret_env_name)
        if secret is None or not secret:
            return UpdateWebhookSecretResult(
                status=UpdateWebhookSecretStatus.INVALID_SECRET,
                webhook=request.webhook,
                error=(
                    f"Environment variable '{request.secret_env_name}' is required "
                    "and must not be empty"
                ),
            )
        update = WebhookSecretUpdate(webhook=request.webhook, secret=secret)
        if not self.registry.update_webhook_secret(update):
            return UpdateWebhookSecretResult(
                status=UpdateWebhookSecretStatus.NOT_FOUND,
                webhook=request.webhook,
                error=f"Webhook '{request.webhook}' is not registered",
            )
        return UpdateWebhookSecretResult(
            status=UpdateWebhookSecretStatus.UPDATED,
            webhook=request.webhook,
        )
