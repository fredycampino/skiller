from __future__ import annotations

import json
from dataclasses import dataclass, field

from stui.adapter.cli_invoker import CliInvoker
from stui.port.notify_action_port import NotifyActionAck, NotifyActionAckStatus


@dataclass(frozen=True)
class CliNotifyActionAdapter:
    invoker: CliInvoker = field(default_factory=CliInvoker)

    def done(self, *, run_id: str, step_id: str) -> NotifyActionAck:
        normalized_run_id = run_id.strip()
        normalized_step_id = step_id.strip()
        if not normalized_run_id:
            return NotifyActionAck(
                status=NotifyActionAckStatus.REJECTED,
                run_id="",
                step_id=normalized_step_id,
                message="error: run_id is required",
            )
        if not normalized_step_id:
            return NotifyActionAck(
                status=NotifyActionAckStatus.REJECTED,
                run_id=normalized_run_id,
                step_id="",
                message="error: step_id is required",
            )

        completed = self.invoker.run("action", "done", normalized_run_id, normalized_step_id)
        payload = _parse_action_done_payload(completed.stdout)
        if payload is None:
            detail = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "runtime command returned invalid JSON"
            )
            return NotifyActionAck(
                status=NotifyActionAckStatus.ERROR,
                run_id=normalized_run_id,
                step_id=normalized_step_id,
                message=f"error: {detail}",
            )

        if payload.done:
            return NotifyActionAck(
                status=NotifyActionAckStatus.ACCEPTED,
                run_id=payload.run_id or normalized_run_id,
                step_id=payload.step_id or normalized_step_id,
            )

        message = payload.error or "notify action done rejected"
        return NotifyActionAck(
            status=NotifyActionAckStatus.REJECTED,
            run_id=payload.run_id or normalized_run_id,
            step_id=payload.step_id or normalized_step_id,
            message=f"error: {message}",
        )


@dataclass(frozen=True)
class ActionDonePayload:
    done: bool
    run_id: str
    step_id: str
    error: str


def _parse_action_done_payload(raw: str) -> ActionDonePayload | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return ActionDonePayload(
        done=bool(payload.get("done")),
        run_id=str(payload.get("run_id", "")).strip(),
        step_id=str(payload.get("step_id", "")).strip(),
        error=str(payload.get("error", "")).strip(),
    )
