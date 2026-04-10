from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from skiller.tools.webhooks import app as webhooks_app


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _request(method: str, path: str, **kwargs: object) -> httpx.Response:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=webhooks_app.create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(run())


def test_health_endpoint() -> None:
    response = _request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_receive_webhook_calls_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"ok": True}
    monkeypatch.setattr(
        webhooks_app,
        "_load_registration",
        lambda webhook: {"webhook": webhook, "secret": "secret", "enabled": True},
    )
    monkeypatch.setattr(
        webhooks_app.launcher,
        "receive_webhook",
        lambda webhook, key, payload, dedup_key=None: {
            "accepted": True,
            "duplicate": False,
            "matched_runs": ["run-1"],
            "webhook": webhook,
            "key": key,
            "dedup_key": dedup_key,
            "payload": payload,
        },
    )

    response = _request(
        "POST",
        "/webhooks/test/42",
        content=_json_bytes(body),
        headers={
            "content-type": "application/json",
            "x-webhook-id": "delivery-1",
            "x-signature": webhooks_app._build_signature("secret", _json_bytes(body)),
        },
    )

    assert response.status_code == 200
    assert response.json()["accepted"] is True
    assert response.json()["matched_runs"] == ["run-1"]
    assert response.json()["webhook"] == "test"
    assert response.json()["key"] == "42"


def test_receive_webhook_rejects_non_object_payload() -> None:
    body = ["bad"]
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        webhooks_app,
        "_load_registration",
        lambda webhook: {"webhook": webhook, "secret": "secret", "enabled": True},
    )
    response = _request(
        "POST",
        "/webhooks/test/42",
        content=_json_bytes(body),
        headers={
            "content-type": "application/json",
            "x-signature": webhooks_app._build_signature("secret", _json_bytes(body)),
        },
    )
    monkeypatch.undo()

    assert response.status_code == 400
    assert response.json()["detail"] == "Payload must be a JSON object"


def test_receive_webhook_requires_signature_when_registered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        webhooks_app,
        "_load_registration",
        lambda webhook: {"webhook": webhook, "secret": "secret", "enabled": True},
    )

    response = _request("POST", "/webhooks/test/42", json={"ok": True})

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing signature"


def test_receive_webhook_rejects_unknown_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webhooks_app, "_load_registration", lambda webhook: None)

    response = _request("POST", "/webhooks/test/42", json={"ok": True})

    assert response.status_code == 404
    assert response.json()["detail"] == "Webhook 'test' is not registered"


def test_receive_webhook_rejects_invalid_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        webhooks_app,
        "_load_registration",
        lambda webhook: {"webhook": webhook, "secret": "secret", "enabled": True},
    )

    response = _request(
        "POST",
        "/webhooks/test/42",
        json={"ok": True},
        headers={"x-signature": "sha256=bad"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid signature"


def test_receive_channel_calls_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webhooks_app, "_is_local_client", lambda request: True)
    monkeypatch.setattr(webhooks_app, "_load_channel_token", lambda: "token-1")
    monkeypatch.setattr(
        webhooks_app.launcher,
        "receive_channel",
        lambda channel, key, payload, external_id=None, dedup_key=None: {
            "accepted": True,
            "duplicate": False,
            "matched_runs": ["run-1"],
            "channel": channel,
            "key": key,
            "external_id": external_id,
            "dedup_key": dedup_key,
            "payload": payload,
        },
    )

    response = _request(
        "POST",
        "/channels/whatsapp/172584771580071@lid",
        json={
            "external_id": "msg-1",
            "dedup_key": "msg-1",
            "payload": {"text": "hola"},
        },
        headers={"x-skiller-channel-token": "token-1"},
    )

    assert response.status_code == 200
    assert response.json()["accepted"] is True
    assert response.json()["matched_runs"] == ["run-1"]
    assert response.json()["channel"] == "whatsapp"
    assert response.json()["key"] == "172584771580071@lid"


def test_receive_channel_requires_local_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webhooks_app, "_is_local_client", lambda request: False)

    response = _request(
        "POST",
        "/channels/whatsapp/172584771580071@lid",
        json={"payload": {"text": "hola"}},
        headers={"x-skiller-channel-token": "token-1"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Channel ingress is local only"


def test_receive_channel_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webhooks_app, "_is_local_client", lambda request: True)
    monkeypatch.setattr(webhooks_app, "_load_channel_token", lambda: "token-1")

    response = _request(
        "POST",
        "/channels/whatsapp/172584771580071@lid",
        json={"payload": {"text": "hola"}},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing channel token"
