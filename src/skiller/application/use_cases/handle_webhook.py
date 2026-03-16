import hashlib
import json
from dataclasses import dataclass
from typing import Any

from skiller.application.ports.state_store_port import StateStorePort


@dataclass(frozen=True)
class HandleWebhookResult:
    accepted: bool
    duplicate: bool
    run_ids: list[str]
    event_id: str | None = None
    error: str | None = None


class HandleWebhookUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(
        self, webhook: str, key: str, payload: dict[str, Any], *, dedup_key: str
    ) -> HandleWebhookResult:
        if not webhook or not key:
            return HandleWebhookResult(
                accepted=False,
                duplicate=False,
                run_ids=[],
                error="webhook and key are required",
            )
        if not isinstance(payload, dict):
            return HandleWebhookResult(
                accepted=False,
                duplicate=False,
                run_ids=[],
                error="payload must be an object",
            )

        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        final_dedup_key = (
            dedup_key
            or hashlib.sha256(f"{webhook}|{key}|{canonical_payload}".encode("utf-8")).hexdigest()
        )

        is_new = self.store.register_webhook_receipt(final_dedup_key, webhook, key, payload)
        if not is_new:
            return HandleWebhookResult(
                accepted=True,
                duplicate=True,
                run_ids=[],
            )

        event_id = self.store.create_webhook_event(webhook, key, payload, final_dedup_key)
        waits = self.store.find_matching_waits(webhook, key)
        run_ids = [str(wait["run_id"]) for wait in waits]
        return HandleWebhookResult(
            accepted=True,
            duplicate=False,
            run_ids=run_ids,
            event_id=event_id,
        )
