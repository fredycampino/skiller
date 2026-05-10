from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from stui.adapter.cli_invoker import CliInvoker
from stui.port.run_port import CommandAck, CommandAckStatus


@dataclass(frozen=True)
class CliWaitingAdapter:
    invoker: CliInvoker = field(default_factory=CliInvoker)

    def send_input(self, *, run_id: str, text: str) -> CommandAck:
        normalized_run_id = run_id.strip()
        normalized_text = text.strip()
        if not normalized_run_id:
            return CommandAck(
                status=CommandAckStatus.REJECTED,
                message="error: run_id is required",
            )
        if not normalized_text:
            return CommandAck(
                status=CommandAckStatus.REJECTED,
                message="error: reply text is required",
            )

        completed = self.invoker.run("input", "receive", normalized_run_id, "--text", text)
        payload = _parse_json_dict(completed.stdout)
        if payload is None:
            detail = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "runtime command returned invalid JSON"
            )
            return CommandAck(status=CommandAckStatus.ERROR, message=f"error: {detail}")

        accepted = bool(payload.get("accepted"))
        error = str(payload.get("error", "")).strip()
        if accepted and not error:
            return CommandAck(status=CommandAckStatus.ACCEPTED, run_id=normalized_run_id)

        message = error or "input rejected"
        return CommandAck(
            status=CommandAckStatus.REJECTED,
            run_id=normalized_run_id,
            message=f"error: {message}",
        )


def _parse_json_dict(raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload
