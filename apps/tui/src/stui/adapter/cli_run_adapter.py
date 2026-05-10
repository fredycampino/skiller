from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field
from typing import Any

from stui.adapter.cli_invoker import CliInvoker
from stui.port.run_port import CommandAck, CommandAckStatus


@dataclass(frozen=True)
class CliRunAdapter:
    invoker: CliInvoker = field(default_factory=CliInvoker)

    def run(self, raw_args: str) -> CommandAck:
        normalized_args = raw_args.strip()
        if not normalized_args:
            return CommandAck(
                status=CommandAckStatus.REJECTED,
                message="error: /run requires arguments",
            )

        try:
            payload = _run_json_command(
                self.invoker,
                "run",
                *shlex.split(normalized_args),
                "--detach",
            )
        except RuntimeError as exc:
            return CommandAck(
                status=CommandAckStatus.ERROR,
                message=f"error: {_sanitize_dispatch_error(str(exc), raw_args=normalized_args)}",
            )

        run_id = str(payload.get("run_id", "")).strip() or None
        status = str(payload.get("status", "UNKNOWN")).strip() or "UNKNOWN"
        short_run_id = run_id[-4:] if run_id else "-"
        message = f"[run-dispatch] {normalized_args}:{short_run_id}\n  ↳ {status.lower()}"
        return CommandAck(
            status=CommandAckStatus.ACCEPTED,
            run_id=run_id,
            message=message,
        )


def _run_json_command(invoker: CliInvoker, *args: str) -> dict[str, Any]:
    completed = invoker.run(*args)

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "runtime command failed"
        raise RuntimeError(detail)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("runtime command returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("runtime command returned invalid payload")

    return payload

def _sanitize_dispatch_error(raw_error: str, *, raw_args: str) -> str:
    normalized = raw_error.strip()
    if not normalized:
        return "runtime command failed"

    skill_ref = raw_args.split()[0].strip() if raw_args.split() else raw_args.strip()

    if "FileNotFoundError: Skill not found:" in normalized:
        if skill_ref:
            return f"agent not found: {skill_ref}"
        return "agent not found"

    for line in normalized.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("FileNotFoundError: Skill not found:"):
            if skill_ref:
                return f"agent not found: {skill_ref}"
            return "agent not found"
        if stripped.startswith("ValueError:"):
            return stripped
        if stripped.startswith("RuntimeError:"):
            return stripped

    return normalized.splitlines()[-1].strip()
