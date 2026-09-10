from __future__ import annotations

import json
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, ValidationError

from stui.adapter.events.cli_log_event import CliLogEvent


class CliObserveStartFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["start"]
    version: int
    run_id: str
    requested_after: int | None
    effective_after: int
    last_sequence: int
    tail: int
    truncated: bool


class CliObserveEventFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["event"]
    event: CliLogEvent


class CliObserveWaitFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["wait"]
    sequence: int
    wait_type: Literal["input", "webhook"]
    prompt: str | None = None


class CliObserveStopFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["stop"]
    sequence: int
    status: Literal["succeeded", "failed", "cancelled"]


CliObserveFrame: TypeAlias = (
    CliObserveStartFrame
    | CliObserveEventFrame
    | CliObserveWaitFrame
    | CliObserveStopFrame
)


def parse_cli_observe_frame(line: bytes) -> CliObserveFrame:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise RuntimeError("observe command returned invalid JSONL") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("observe command returned invalid frame")

    kind = payload.get("kind")
    try:
        if kind == "start":
            return CliObserveStartFrame.model_validate(payload)
        if kind == "event":
            return CliObserveEventFrame.model_validate(payload)
        if kind == "wait":
            return CliObserveWaitFrame.model_validate(payload)
        if kind == "stop":
            return CliObserveStopFrame.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError(f"observe command returned invalid frame: {exc}") from exc

    raise RuntimeError("observe command returned unknown frame")
