from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from skiller.domain.run.run_model import RunStatus
from skiller.interfaces.tui.port.run_port import PollingEvent, PollingEventKind


@dataclass(frozen=True)
class RunLogRecord:
    event_id: str
    event_type: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class RunStatusRecord:
    status: str


class RunEventMapper:
    def logs_to_events(
        self,
        *,
        run_id: str,
        events_payload: list[dict[str, Any]],
        seen_event_ids: set[str],
    ) -> list[PollingEvent]:
        observed: list[PollingEvent] = []
        for raw_event in events_payload:
            record = _parse_run_log_record(raw_event)
            if record is None or record.event_id in seen_event_ids:
                continue

            seen_event_ids.add(record.event_id)
            text = _format_watch_event(run_id, record)
            if not text:
                continue

            observed.append(
                PollingEvent(
                    kind=PollingEventKind.LOG,
                    run_id=run_id,
                    text=text,
                    event_type=record.event_type,
                    skill=_string_field(record.payload, "skill"),
                    step=_string_field(record.payload, "step"),
                    step_type=_string_field(record.payload, "step_type"),
                    output=_compact_output(record.payload.get("output")),
                    error=_string_field(record.payload, "error"),
                    event_id=record.event_id,
                )
            )

        return observed

    def status_to_event(
        self,
        *,
        run_id: str,
        status_payload: dict[str, Any],
        last_status: str,
    ) -> PollingEvent | None:
        record = _parse_run_status_record(status_payload)
        if record is None or record.status == last_status:
            return None

        return PollingEvent(
            kind=PollingEventKind.STATUS,
            run_id=run_id,
            status=record.status,
            text=f"[{_display_run_id(run_id)}] {record.status}",
        )


def _parse_run_log_record(raw_event: dict[str, Any]) -> RunLogRecord | None:
    event_id = str(raw_event.get("id", "")).strip()
    event_type = str(raw_event.get("type", "")).strip().upper()
    if not event_id or not event_type:
        return None

    payload = raw_event.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}

    return RunLogRecord(
        event_id=event_id,
        event_type=event_type,
        payload=payload,
    )


def _parse_run_status_record(status_payload: dict[str, Any]) -> RunStatusRecord | None:
    status = str(status_payload.get("status", "")).strip().upper()
    if not status:
        return None

    return RunStatusRecord(status=status)


def _format_watch_event(run_id: str, record: RunLogRecord) -> str | None:
    event_type = record.event_type
    payload = record.payload
    if not payload:
        return f"[{_display_run_id(run_id)}] {event_type}"

    parts: list[str]
    if event_type == "RUN_CREATE":
        parts = [
            _format_field("skill", payload.get("skill")),
            _format_field("skill_source", payload.get("skill_source")),
        ]
    elif event_type == "RUN_RESUME":
        parts = [_format_field("source", payload.get("source"))]
    elif event_type == "STEP_STARTED":
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("step_type", payload.get("step_type")),
        ]
    elif event_type == "STEP_SUCCESS":
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("step_type", payload.get("step_type")),
            _format_field("output", payload.get("output")),
            _format_field("next", payload.get("next")),
        ]
    elif event_type == "STEP_ERROR":
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("step_type", payload.get("step_type")),
            _format_field("error", payload.get("error")),
        ]
    elif event_type == "RUN_WAITING":
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("step_type", payload.get("step_type")),
            _format_field("output", payload.get("output")),
        ]
    elif event_type == "RUN_FINISHED":
        status = str(payload.get("status", "")).upper()
        if status == RunStatus.SUCCEEDED.value:
            return None
        parts = [
            _format_field("status", payload.get("status")),
            _format_field("error", payload.get("error")),
        ]
    else:
        parts = [_format_field(key, value) for key, value in payload.items()]

    rendered_parts = [part for part in parts if part]
    if not rendered_parts:
        return f"[{_display_run_id(run_id)}] {event_type}"
    return f"[{_display_run_id(run_id)}] {event_type} {' '.join(rendered_parts)}"


def _display_run_id(run_id: str) -> str:
    normalized = str(run_id).strip()
    if not normalized:
        return "-"
    tail = normalized.rsplit("-", 1)[-1]
    if len(tail) >= 4:
        return tail[-4:]
    if tail:
        return tail
    if len(normalized) <= 4:
        return normalized
    return normalized[-4:]


def _format_field(name: str, value: Any) -> str:
    if value is None:
        return ""
    return f"{name}={_compact_value(value)}"


def _string_field(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if value is None:
        return ""
    return str(value).strip()


def _compact_output(value: Any) -> str:
    if value is None:
        return ""
    return _compact_value(value)


def _compact_value(value: Any) -> str:
    if isinstance(value, str):
        raw = json.dumps(value, ensure_ascii=True)
    else:
        raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    if len(raw) <= 120:
        return raw
    return f"{raw[:117]}..."
