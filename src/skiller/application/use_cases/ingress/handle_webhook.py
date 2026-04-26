import hashlib
import json
from dataclasses import dataclass
from typing import Any

from skiller.application.ports.external_event_store_port import ExternalEventStorePort
from skiller.application.ports.wait_store_port import WaitStorePort
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType


@dataclass(frozen=True)
class HandleWebhookResult:
    accepted: bool
    duplicate: bool
    run_ids: list[str]
    event_id: str | None = None
    error: str | None = None


class HandleWebhookUseCase:
    def __init__(
        self,
        external_event_store: ExternalEventStorePort,
        wait_store: WaitStorePort,
    ) -> None:
        self.external_event_store = external_event_store
        self.wait_store = wait_store

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

        is_new = self.external_event_store.register_external_receipt(
            final_dedup_key,
            SourceType.WEBHOOK,
            webhook,
            MatchType.SIGNAL,
            key,
            payload,
        )
        if not is_new:
            return HandleWebhookResult(
                accepted=True,
                duplicate=True,
                run_ids=[],
            )

        event_id = self.external_event_store.create_external_event(
            source_type=SourceType.WEBHOOK,
            source_name=webhook,
            match_type=MatchType.SIGNAL,
            match_key=key,
            dedup_key=final_dedup_key,
            payload=payload,
        )
        waits = self.wait_store.find_matching_waits(
            source_type=SourceType.WEBHOOK,
            source_name=webhook,
            match_type=MatchType.SIGNAL,
            match_key=key,
        )
        run_ids = self._select_run_ids(waits)
        return HandleWebhookResult(
            accepted=True,
            duplicate=False,
            run_ids=run_ids,
            event_id=event_id,
        )

    def _select_run_ids(self, waits: list[dict[str, object]]) -> list[str]:
        if not waits:
            return []

        run_id = str(waits[0].get("run_id", "")).strip()
        if not run_id:
            return []
        return [run_id]
