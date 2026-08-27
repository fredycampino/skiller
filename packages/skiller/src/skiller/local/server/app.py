from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from skiller.domain.event.webhook_registration_model import WebhookRegistration
from skiller.infrastructure.config.settings import get_settings
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.local.server import launcher


def _load_registration(webhook: str) -> WebhookRegistration | None:
    settings = get_settings()
    registry = SqliteWebhookRegistry(settings.db_path)
    return registry.get_webhook_registration(webhook)


def _build_signature(secret: str, raw_body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _validate_webhook_token(request: Request, registration: WebhookRegistration) -> None:
    token_header = registration.token_header
    if token_header is None:
        raise HTTPException(status_code=500, detail="Invalid webhook token configuration")
    received_token = request.headers.get(token_header)
    if not received_token:
        raise HTTPException(status_code=401, detail="Missing webhook token")
    if not hmac.compare_digest(
        received_token.encode("utf-8"), registration.secret.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook token")


def _channel_token_file() -> Path:
    home = Path.home()
    return home / ".skiller" / "channels" / "token.txt"


def _load_channel_token() -> str | None:
    token_file = _channel_token_file()
    if not token_file.exists():
        return None
    token = token_file.read_text(encoding="utf-8").strip()
    return token or None


def _is_local_client(request: Request) -> bool:
    host = (request.client.host if request.client else "").strip()
    return host in {"127.0.0.1", "::1", "localhost"}


def create_app() -> Any:
    app = FastAPI(title="Skiller Webhooks", version="1.0.0-alpha.3")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    async def handle_webhook_request(
        *,
        method: str,
        webhook: str,
        key: str,
        request: Request,
        x_signature: str | None,
        x_webhook_id: str | None,
    ) -> dict[str, Any]:
        registration = _load_registration(webhook)
        if registration is None:
            raise HTTPException(status_code=404, detail=f"Webhook '{webhook}' is not registered")
        if not registration.enabled:
            raise HTTPException(status_code=403, detail=f"Webhook '{webhook}' is disabled")
        if method != registration.method.value:
            raise HTTPException(status_code=405, detail="Webhook method is not allowed")

        auth = registration.auth.value
        if auth not in {"signed", "token", "none"}:
            raise HTTPException(status_code=500, detail="Invalid webhook auth configuration")
        if auth == "token":
            _validate_webhook_token(request, registration)

        raw_body = await request.body()
        if auth == "signed":
            if not x_signature:
                raise HTTPException(status_code=401, detail="Missing signature")
            expected_signature = _build_signature(registration.secret, raw_body)
            if not hmac.compare_digest(x_signature, expected_signature):
                raise HTTPException(status_code=401, detail="Invalid signature")

        payload_source = registration.payload_source.value
        if payload_source not in {"body_json", "query"}:
            raise HTTPException(status_code=500, detail="Invalid webhook payload configuration")
        if payload_source == "body_json":
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=400,
                    detail="Payload must be a JSON object",
                ) from exc
        else:
            payload = dict(request.query_params)

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Payload must be a JSON object")

        try:
            return launcher.receive_webhook(webhook, key, payload, dedup_key=x_webhook_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/webhooks/{webhook}/{key}")
    async def receive_webhook_post(
        webhook: str,
        key: str,
        request: Request,
        x_signature: str | None = Header(default=None),
        x_webhook_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return await handle_webhook_request(
            method="POST",
            webhook=webhook,
            key=key,
            request=request,
            x_signature=x_signature,
            x_webhook_id=x_webhook_id,
        )

    @app.get("/webhooks/{webhook}/{key}")
    async def receive_webhook_get(
        webhook: str,
        key: str,
        request: Request,
        x_signature: str | None = Header(default=None),
        x_webhook_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return await handle_webhook_request(
            method="GET",
            webhook=webhook,
            key=key,
            request=request,
            x_signature=x_signature,
            x_webhook_id=x_webhook_id,
        )

    @app.post("/channels/{channel}/{key}")
    async def receive_channel(
        channel: str,
        key: str,
        request: Request,
        x_skiller_channel_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if not _is_local_client(request):
            raise HTTPException(status_code=403, detail="Channel ingress is local only")

        expected_token = _load_channel_token()
        if expected_token is None:
            raise HTTPException(status_code=503, detail="Channel ingress is not configured")
        if not x_skiller_channel_token:
            raise HTTPException(status_code=401, detail="Missing channel token")
        if not hmac.compare_digest(x_skiller_channel_token, expected_token):
            raise HTTPException(status_code=401, detail="Invalid channel token")

        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Payload must be a JSON object") from exc

        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Payload must be a JSON object")

        payload = body.get("payload")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Payload must include a JSON object")

        external_id = body.get("external_id")
        dedup_key = body.get("dedup_key")
        if external_id is not None and not isinstance(external_id, str):
            raise HTTPException(status_code=400, detail="external_id must be a string")
        if dedup_key is not None and not isinstance(dedup_key, str):
            raise HTTPException(status_code=400, detail="dedup_key must be a string")

        try:
            return launcher.receive_channel(
                channel,
                key,
                payload,
                external_id=external_id,
                dedup_key=dedup_key,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app
