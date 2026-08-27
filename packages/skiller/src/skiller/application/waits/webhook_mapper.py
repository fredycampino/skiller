import re
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
WEBHOOK_TOKEN_HEADER_ERROR = "webhook token authentication requires token_header"
WEBHOOK_TOKEN_HEADER_UNSUPPORTED_ERROR = "token_header is only supported with token authentication"
WEBHOOK_TOKEN_HEADER_INVALID_ERROR = "token_header must be a valid HTTP field name"
HTTP_FIELD_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


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
        token_header: str | None,
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
        normalized_token_header = (token_header or "").strip() or None
        if parsed_auth == WebhookAuth.TOKEN and normalized_token_header is None:
            raise ValueError(WEBHOOK_TOKEN_HEADER_ERROR)
        if (
            normalized_token_header is not None
            and not HTTP_FIELD_NAME.fullmatch(normalized_token_header)
        ):
            raise ValueError(WEBHOOK_TOKEN_HEADER_INVALID_ERROR)
        if parsed_auth != WebhookAuth.TOKEN and normalized_token_header is not None:
            raise ValueError(WEBHOOK_TOKEN_HEADER_UNSUPPORTED_ERROR)

        return RegisterWebhookInput(
            webhook=webhook.strip(),
            method=parsed_method,
            auth=parsed_auth,
            payload_source=parsed_payload_source,
            token_header=normalized_token_header,
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
        if result.token_header is not None:
            payload["token_header"] = result.token_header
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
        return [
            {
                "webhook": registration.webhook,
                "secret": registration.secret,
                "method": registration.method.value,
                "auth": registration.auth.value,
                "payload_source": registration.payload_source.value,
                "token_header": registration.token_header,
                "enabled": registration.enabled,
                "created_at": registration.created_at,
            }
            for registration in result.webhooks
        ]

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
