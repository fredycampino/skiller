from __future__ import annotations

import json

from pydantic import TypeAdapter, ValidationError

from stui.adapter.cli_agent_interrupt import (
    CliAgentInterrupt,
    CliAgentInterruptRejected,
)
from stui.port.run_port import CommandAck, CommandAckStatus

CLI_AGENT_INTERRUPT_ADAPTER = TypeAdapter(CliAgentInterrupt)


class AgentInterruptMapper:
    def map(self, raw: str) -> CommandAck:
        payload = _load_json(raw)
        model = _validate_model(payload)
        if isinstance(model, CliAgentInterruptRejected):
            return CommandAck(
                status=CommandAckStatus.ERROR,
                run_id=model.run_id,
                message=f"error: {model.error}",
            )

        return CommandAck(
            status=CommandAckStatus.ACCEPTED,
            run_id=model.run_id,
            message=f"[agent-interrupt] {model.run_id}\n  ↳ {model.status.lower()}",
        )


def _load_json(raw: str) -> object:
    if not isinstance(raw, str):
        raise RuntimeError("agent interrupt command returned invalid JSON")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("agent interrupt command returned invalid JSON") from exc


def _validate_model(payload: object) -> CliAgentInterrupt:
    try:
        return CLI_AGENT_INTERRUPT_ADAPTER.validate_python(payload)
    except ValidationError as exc:
        raise RuntimeError(
            f"agent interrupt command returned invalid payload: {exc}"
        ) from exc
