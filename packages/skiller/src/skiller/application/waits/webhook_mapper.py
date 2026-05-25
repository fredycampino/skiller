from typing import Any

from skiller.application.use_cases.ingress.handle_webhook import (
    HandleWebhookInput,
    HandleWebhookResult,
)
from skiller.application.use_cases.query.list_webhooks import ListWebhooksResult
from skiller.application.use_cases.webhook.register_webhook import (
    RegisterWebhookInput,
    RegisterWebhookResult,
    RegisterWebhookStatus,
)
from skiller.application.use_cases.webhook.remove_webhook import (
    RemoveWebhookResult,
    RemoveWebhookStatus,
)
from skiller.domain.event.webhook_registration_model import (
    WebhookAuth,
    WebhookMethod,
    WebhookPayloadSource,
)

WEBHOOK_CONFIG_ERROR = "webhook method and payload source must be POST/body_json or GET/query"


class WebhookWaitMapper:
    def to_handle_input(
        self,
        webhook: str,
        key: str,
        payload: dict[str, Any],
        dedup_key: str | None = None,
    ) -> HandleWebhookInput:
        return HandleWebhookInput(
            webhook=webhook.strip(),
            key=key.strip(),
            payload=payload,
            dedup_key=(dedup_key or "").strip(),
        )

    def to_handle_dict(
        self,
        request: HandleWebhookInput,
        result: HandleWebhookResult,
    ) -> dict[str, Any]:
        return {
            "accepted": result.accepted,
            "duplicate": result.duplicate,
            "webhook": request.webhook,
            "key": request.key,
            "matched_runs": result.run_ids,
        }

    def to_register_input(
        self,
        webhook: str,
        *,
        method: str,
        auth: str,
        payload_source: str,
    ) -> RegisterWebhookInput:
        parsed_method = self._parse_method(method)
        parsed_auth = self._parse_auth(auth)
        parsed_payload_source = self._parse_payload_source(payload_source)

        valid_pair = (
            parsed_method,
            parsed_payload_source,
        ) in {
            (WebhookMethod.POST, WebhookPayloadSource.BODY_JSON),
            (WebhookMethod.GET, WebhookPayloadSource.QUERY),
        }
        if not valid_pair:
            raise ValueError(WEBHOOK_CONFIG_ERROR)

        return RegisterWebhookInput(
            webhook=webhook.strip(),
            method=parsed_method,
            auth=parsed_auth,
            payload_source=parsed_payload_source,
        )

    def to_register_dict(self, result: RegisterWebhookResult) -> dict[str, Any]:
        payload = {
            "webhook": result.webhook,
            "status": result.status.value,
            "method": result.method.value,
            "auth": result.auth.value,
            "payload_source": result.payload_source.value,
        }
        if result.secret is not None:
            payload["secret"] = result.secret
        if result.enabled is not None:
            payload["enabled"] = result.enabled
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def to_register_error_dict(self, webhook: str, error: str) -> dict[str, Any]:
        return {
            "webhook": webhook,
            "status": RegisterWebhookStatus.INVALID_CONFIG.value,
            "error": error,
        }

    def to_list_dict(self, result: ListWebhooksResult) -> list[dict[str, Any]]:
        return result.webhooks

    def to_remove_input(self, webhook: str) -> str:
        return webhook.strip()

    def to_remove_dict(self, result: RemoveWebhookResult) -> dict[str, Any]:
        payload = {
            "webhook": result.webhook,
            "status": result.status.value,
            "removed": result.status == RemoveWebhookStatus.REMOVED,
        }
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def _parse_method(self, method: str) -> WebhookMethod:
        try:
            return WebhookMethod(method.strip().upper())
        except ValueError as exc:
            raise ValueError(WEBHOOK_CONFIG_ERROR) from exc

    def _parse_auth(self, auth: str) -> WebhookAuth:
        try:
            return WebhookAuth(auth.strip().lower())
        except ValueError as exc:
            raise ValueError(WEBHOOK_CONFIG_ERROR) from exc

    def _parse_payload_source(self, payload_source: str) -> WebhookPayloadSource:
        try:
            return WebhookPayloadSource(payload_source.strip().lower())
        except ValueError as exc:
            raise ValueError(WEBHOOK_CONFIG_ERROR) from exc
