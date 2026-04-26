import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from skiller.application.ports.external_event_store_port import ExternalEventStorePort
from skiller.application.ports.wait_store_port import WaitStorePort
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType


@dataclass(frozen=True)
class HandleChannelResult:
    accepted: bool
    duplicate: bool
    run_ids: list[str]
    event_id: str | None = None
    error: str | None = None


class HandleChannelUseCase:
    def __init__(
        self,
        external_event_store: ExternalEventStorePort,
        wait_store: WaitStorePort,
    ) -> None:
        self.external_event_store = external_event_store
        self.wait_store = wait_store

    def execute(
        self,
        channel: str,
        key: str,
        payload: dict[str, Any],
        *,
        external_id: str | None = None,
        dedup_key: str,
    ) -> HandleChannelResult:
        if not channel or not key:
            return HandleChannelResult(
                accepted=False,
                duplicate=False,
                run_ids=[],
                error="channel and key are required",
            )
        if not isinstance(payload, dict):
            return HandleChannelResult(
                accepted=False,
                duplicate=False,
                run_ids=[],
                error="payload must be an object",
            )

        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        final_dedup_key = (
            dedup_key
            or external_id
            or hashlib.sha256(
                f"{channel}|{key}|{canonical_payload}".encode("utf-8")
            ).hexdigest()
        )

        is_new = self.external_event_store.register_external_receipt(
            final_dedup_key,
            SourceType.CHANNEL,
            channel,
            MatchType.CHANNEL_KEY,
            key,
            payload,
        )
        if not is_new:
            return HandleChannelResult(
                accepted=True,
                duplicate=True,
                run_ids=[],
            )

        waits = self.wait_store.find_matching_waits(
            source_type=SourceType.CHANNEL,
            source_name=channel,
            match_type=MatchType.CHANNEL_KEY,
            match_key=key,
        )
        fresh_waits = _filter_waits_for_payload_timestamp(waits=waits, payload=payload)
        if waits and not fresh_waits:
            return HandleChannelResult(
                accepted=True,
                duplicate=False,
                run_ids=[],
            )

        event_id = self.external_event_store.create_external_event(
            source_type=SourceType.CHANNEL,
            source_name=channel,
            match_type=MatchType.CHANNEL_KEY,
            match_key=key,
            external_id=external_id,
            dedup_key=final_dedup_key,
            payload=payload,
        )
        run_ids = self._select_run_ids(fresh_waits)
        return HandleChannelResult(
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


def _filter_waits_for_payload_timestamp(
    *,
    waits: list[dict[str, object]],
    payload: dict[str, Any],
) -> list[dict[str, object]]:
    message_timestamp = _payload_timestamp_epoch(payload)
    if message_timestamp is None:
        return waits

    fresh_waits: list[dict[str, object]] = []
    for wait in waits:
        wait_created_at = _wait_created_at_epoch(wait)
        if wait_created_at is None or message_timestamp >= wait_created_at:
            fresh_waits.append(wait)
    return fresh_waits


def _payload_timestamp_epoch(payload: dict[str, Any]) -> float | None:
    raw_timestamp = payload.get("timestamp")
    if raw_timestamp is None:
        return None
    try:
        timestamp = float(raw_timestamp)
    except (TypeError, ValueError):
        return None
    if timestamp > 10_000_000_000:
        return timestamp / 1000
    return timestamp


def _wait_created_at_epoch(wait: dict[str, object]) -> float | None:
    raw_created_at = str(wait.get("created_at", "")).strip()
    if not raw_created_at:
        return None
    normalized = raw_created_at.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()
