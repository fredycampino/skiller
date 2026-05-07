from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from skiller.interfaces.tui.adapter.cli_invoker import CliInvoker
from skiller.interfaces.tui.port.run_port import CommandAck, CommandAckStatus


@dataclass(frozen=True)
class CliAgentAdapter:
    invoker: CliInvoker = field(default_factory=CliInvoker)

    def interrupt(self, run_id: str) -> CommandAck:
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            return CommandAck(
                status=CommandAckStatus.REJECTED,
                message="error: run_id is required",
            )

        completed = self.invoker.run("agent", "interrupt", normalized_run_id)
        payload = _parse_json_dict(completed.stdout)
        if payload is None:
            detail = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "runtime command returned invalid JSON"
            )
            return CommandAck(status=CommandAckStatus.ERROR, message=f"error: {detail}")

        error = str(payload.get("error", "")).strip()
        if completed.returncode == 0 and not error:
            status = str(payload.get("status", "")).strip().upper() or "ENQUEUED"
            return CommandAck(
                status=CommandAckStatus.ACCEPTED,
                run_id=normalized_run_id,
                message=f"[agent-interrupt] {normalized_run_id}\n  ↳ {status.lower()}",
            )

        message = error or completed.stderr.strip() or "agent interrupt failed"
        return CommandAck(
            status=CommandAckStatus.ERROR,
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
