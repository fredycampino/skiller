from __future__ import annotations

import json
from dataclasses import dataclass, field

from stui.adapter.cli_invoker import CliInvoker
from stui.port.waiting_port import WaitingInputAck, WaitingInputStatus


@dataclass(frozen=True)
class CliWaitingAdapter:
    invoker: CliInvoker = field(default_factory=CliInvoker)

    def send_input(self, *, run_id: str, text: str) -> WaitingInputAck:
        normalized_run_id = run_id.strip()
        normalized_text = text.strip()
        if not normalized_run_id:
            return WaitingInputAck(
                status=WaitingInputStatus.REJECTED,
                run_id="",
                message="error: run_id is required",
            )
        if not normalized_text:
            return WaitingInputAck(
                status=WaitingInputStatus.REJECTED,
                run_id=normalized_run_id,
                message="error: reply text is required",
            )

        completed = self.invoker.run("input", "receive", normalized_run_id, "--text", text)
        payload = _parse_waiting_input_payload(completed.stdout)
        if payload is None:
            detail = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "runtime command returned invalid JSON"
            )
            return WaitingInputAck(
                status=WaitingInputStatus.ERROR,
                run_id=normalized_run_id,
                message=f"error: {detail}",
            )

        if payload.accepted and not payload.error and payload.run_id:
            return WaitingInputAck(
                status=WaitingInputStatus.ACCEPTED,
                run_id=payload.run_id,
                message="",
            )
        if payload.accepted and not payload.run_id:
            return WaitingInputAck(
                status=WaitingInputStatus.ERROR,
                run_id=normalized_run_id,
                message="error: runtime command returned no run_id",
            )

        message = payload.error or "input rejected"
        return WaitingInputAck(
            status=WaitingInputStatus.REJECTED,
            run_id=normalized_run_id,
            message=f"error: {message}",
        )


@dataclass(frozen=True)
class WaitingInputPayload:
    accepted: bool
    run_id: str
    error: str


def _parse_waiting_input_payload(raw: str) -> WaitingInputPayload | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return WaitingInputPayload(
        accepted=bool(payload.get("accepted")),
        run_id=str(payload.get("run_id", "")).strip(),
        error=str(payload.get("error", "")).strip(),
    )
