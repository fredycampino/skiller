from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any


def receive_webhook(
    webhook: str,
    key: str,
    payload: dict[str, Any],
    *,
    dedup_key: str | None = None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "skiller",
        "webhook",
        "receive",
        webhook,
        key,
        "--json",
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
    ]
    if dedup_key:
        command.extend(["--dedup-key", dedup_key])

    completed = subprocess.run(  # noqa: S603
        command,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    if completed.returncode != 0:
        detail = (
            completed.stderr.strip() or completed.stdout.strip() or "webhook receive command failed"
        )
        raise RuntimeError(detail)

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("webhook receive command returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("webhook receive command returned invalid payload")
    return result


def receive_channel(
    channel: str,
    key: str,
    payload: dict[str, Any],
    *,
    external_id: str | None = None,
    dedup_key: str | None = None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "skiller",
        "channel",
        "receive",
        channel,
        key,
        "--json",
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
    ]
    if external_id:
        command.extend(["--external-id", external_id])
    if dedup_key:
        command.extend(["--dedup-key", dedup_key])

    completed = subprocess.run(  # noqa: S603
        command,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    if completed.returncode != 0:
        detail = (
            completed.stderr.strip() or completed.stdout.strip() or "channel receive command failed"
        )
        raise RuntimeError(detail)

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("channel receive command returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("channel receive command returned invalid payload")
    return result
