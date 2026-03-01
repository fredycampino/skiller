from typing import Any

from runtime.application.factory import build_runtime_container


def create_app() -> Any:
    from fastapi import FastAPI, Header, HTTPException, Request

    container = build_runtime_container()
    bootstrap = container.bootstrap
    settings = container.settings
    runtime = container.runtime
    bootstrap.initialize()

    app = FastAPI(title="Agent Runtime POC", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhooks/{key}")
    async def webhook(
        key: str,
        request: Request,
        x_signature: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Payload must be a JSON object")

        if settings.webhook_secret and not x_signature:
            raise HTTPException(status_code=401, detail="Missing signature")

        matched_runs = runtime.handle_webhook(key, payload)
        return {"accepted": True, "matched_runs": matched_runs}

    return app
