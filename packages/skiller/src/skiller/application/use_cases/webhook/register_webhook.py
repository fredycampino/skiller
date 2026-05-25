import secrets
from dataclasses import dataclass
from enum import Enum

from skiller.domain.event.webhook_registration_model import (
    WebhookAuth,
    WebhookMethod,
    WebhookPayloadSource,
)
from skiller.domain.event.webhook_registry_port import WebhookRegistryPort


@dataclass(frozen=True)
class RegisterWebhookInput:
    webhook: str
    method: WebhookMethod
    auth: WebhookAuth
    payload_source: WebhookPayloadSource


class RegisterWebhookStatus(str, Enum):
    REGISTERED = "REGISTERED"
    INVALID_WEBHOOK = "INVALID_WEBHOOK"
    INVALID_CONFIG = "INVALID_CONFIG"
    ALREADY_REGISTERED = "ALREADY_REGISTERED"


@dataclass(frozen=True)
class RegisterWebhookResult:
    status: RegisterWebhookStatus
    webhook: str
    method: WebhookMethod
    auth: WebhookAuth
    payload_source: WebhookPayloadSource
    secret: str | None = None
    enabled: bool | None = None
    error: str | None = None


class RegisterWebhookUseCase:
    def __init__(self, registry: WebhookRegistryPort) -> None:
        self.registry = registry

    def execute(
        self,
        request: RegisterWebhookInput,
    ) -> RegisterWebhookResult:
        normalized = request.webhook
        if not normalized:
            return RegisterWebhookResult(
                status=RegisterWebhookStatus.INVALID_WEBHOOK,
                webhook=request.webhook,
                method=request.method,
                auth=request.auth,
                payload_source=request.payload_source,
                error="webhook is required",
            )

        existing = self.registry.get_webhook_registration(normalized)
        if existing is not None:
            return RegisterWebhookResult(
                status=RegisterWebhookStatus.ALREADY_REGISTERED,
                webhook=normalized,
                method=request.method,
                auth=request.auth,
                payload_source=request.payload_source,
                error=f"Webhook '{normalized}' is already registered",
            )

        secret = secrets.token_urlsafe(32)
        self.registry.register_webhook(
            normalized,
            secret,
            method=request.method,
            auth=request.auth,
            payload_source=request.payload_source,
        )
        return RegisterWebhookResult(
            status=RegisterWebhookStatus.REGISTERED,
            webhook=normalized,
            method=request.method,
            auth=request.auth,
            payload_source=request.payload_source,
            secret=secret,
            enabled=True,
        )
