from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from typing import Any


def execute_run(*, raw_args: str) -> dict[str, Any]:
    normalized_args = raw_args.strip()
    if not normalized_args:
        raise RuntimeError("run command requires skill args, for example: /run notify_test")

    command = [
        sys.executable,
        "-m",
        "skiller",
        "run",
        *shlex.split(normalized_args),
    ]

    completed = subprocess.run(  # noqa: S603
        command,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "run command failed"
        raise RuntimeError(detail)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("run command returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("run command returned invalid payload")

    return payload
