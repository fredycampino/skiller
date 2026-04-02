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

    return _run_json_command("run", *shlex.split(normalized_args), "--detach")


class CliRuntimeAdapter:
    def run(self, *, raw_args: str) -> dict[str, Any]:
        return execute_run(raw_args=raw_args)

    def server_status(self) -> dict[str, Any]:
        return _run_json_command("server", "status")

    def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, Any]]:
        args = ["runs"]
        for status in statuses or []:
            args.extend(["--status", status])
        payload = _run_json_command(*args)
        if not isinstance(payload, list):
            raise RuntimeError("runs command returned invalid payload")
        return payload

    def webhooks(self) -> list[dict[str, Any]]:
        payload = _run_json_command("webhook", "list")
        if not isinstance(payload, list):
            raise RuntimeError("webhook list command returned invalid payload")
        return payload

    def status(self, *, run_id: str) -> dict[str, Any]:
        return _run_json_command("status", run_id)

    def logs(self, *, run_id: str) -> list[dict[str, Any]]:
        payload = _run_json_command("logs", run_id)
        if not isinstance(payload, list):
            raise RuntimeError("logs command returned invalid payload")
        return payload

    def get_execution_output(self, *, body_ref: str) -> dict[str, Any] | None:
        payload = _run_json_command("execution-output", body_ref)
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise RuntimeError("execution-output command returned invalid payload")
        return payload

    def watch(self, *, run_id: str) -> dict[str, Any]:
        return _run_watch_command(run_id)

    def input_receive(self, *, run_id: str, text: str) -> dict[str, Any]:
        return _run_json_command("input", "receive", run_id, "--text", text)

    def resume(self, *, run_id: str) -> dict[str, Any]:
        return _run_json_command("resume", run_id)


def _run_json_command(*args: str) -> Any:
    completed = _run_cli_command(*args)

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "runtime command failed"
        raise RuntimeError(detail)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("runtime command returned invalid JSON") from exc

    return payload


def _run_watch_command(run_id: str) -> dict[str, Any]:
    completed = _run_cli_command("watch", run_id)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "watch command failed"
            raise RuntimeError(detail) from exc
        raise RuntimeError("watch command returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("watch command returned invalid payload")

    return payload


def _run_cli_command(*args: str) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "skiller",
        *args,
    ]

    return subprocess.run(  # noqa: S603
        command,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
