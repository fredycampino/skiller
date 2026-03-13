from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from skiller.infrastructure.config.settings import get_settings
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.tools.webhooks import launcher


def _load_registration(webhook: str) -> dict[str, Any] | None:
    settings = get_settings()
    registry = SqliteWebhookRegistry(settings.db_path)
    return registry.get_webhook_registration(webhook)


def _build_signature(secret: str, raw_body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def create_app() -> Any:
    app = FastAPI(title="Skiller Webhooks", version="1.0.0-alpha.3")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhooks/{webhook}/{key}")
    async def receive_webhook(
        webhook: str,
        key: str,
        request: Request,
        x_signature: str | None = Header(default=None),
        x_webhook_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        registration = _load_registration(webhook)
        if registration is None:
            raise HTTPException(status_code=404, detail=f"Webhook '{webhook}' is not registered")
        if not bool(registration.get("enabled", False)):
            raise HTTPException(status_code=403, detail=f"Webhook '{webhook}' is disabled")
        if not x_signature:
            raise HTTPException(status_code=401, detail="Missing signature")

        raw_body = await request.body()
        expected_signature = _build_signature(str(registration["secret"]), raw_body)
        if not hmac.compare_digest(x_signature, expected_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Payload must be a JSON object") from exc

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Payload must be a JSON object")

        try:
            return launcher.receive_webhook(webhook, key, payload, dedup_key=x_webhook_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app
