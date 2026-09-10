from __future__ import annotations

import json
from typing import Any

import pytest

from stui.adapter.events.cli_observe_frame import (
    CliObserveEventFrame,
    CliObserveStartFrame,
    CliObserveStopFrame,
    CliObserveWaitFrame,
    parse_cli_observe_frame,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("payload", "frame_type"),
    [
        (
            {
                "kind": "start",
                "version": 1,
                "run_id": "run-1",
                "requested_after": None,
                "effective_after": 0,
                "last_sequence": 0,
                "tail": 100,
                "truncated": False,
            },
            CliObserveStartFrame,
        ),
        (
            {
                "kind": "event",
                "event": {
                    "sequence": 1,
                    "id": "event-1",
                    "run_id": "run-1",
                    "type": "STEP_STARTED",
                    "step_id": "agent",
                    "step_type": "agent",
                    "agent_sequence": None,
                    "created_at": "2026-05-12T10:30:15Z",
                    "payload": {},
                },
            },
            CliObserveEventFrame,
        ),
        (
            {"kind": "wait", "sequence": 1, "wait_type": "input", "prompt": "Continue?"},
            CliObserveWaitFrame,
        ),
        (
            {"kind": "stop", "sequence": 2, "status": "succeeded"},
            CliObserveStopFrame,
        ),
    ],
)
def test_parse_cli_observe_frame_parses_protocol_frames(
    payload: dict[str, Any],
    frame_type: type[object],
) -> None:
    frame = parse_cli_observe_frame(json.dumps(payload).encode())

    assert isinstance(frame, frame_type)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (b"not-json", "invalid JSONL"),
        (b"[]", "invalid frame"),
        (b'{"kind":"unknown"}', "unknown frame"),
        (b'{"kind":"start"}', "invalid frame"),
        (
            b'{"kind":"stop","sequence":1,"status":"succeeded","extra":true}',
            "invalid frame",
        ),
        (b'{"kind":"wait","sequence":1,"wait_type":"channel"}', "invalid frame"),
        (b'{"kind":"stop","sequence":1,"status":"running"}', "invalid frame"),
        (b'{"kind":"event","event":{"sequence":1}}', "invalid frame"),
    ],
)
def test_parse_cli_observe_frame_rejects_invalid_protocol_frames(
    line: bytes,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        parse_cli_observe_frame(line)
