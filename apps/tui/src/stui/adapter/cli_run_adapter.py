from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field
from typing import Any

from stui.adapter.cli_invoker import CliInvoker
from stui.port.run_port import (
    RunDispatch,
    RunDispatchError,
    RunDispatchErrorKind,
    RunRuntimeStatus,
    RunRuntimeStatusKind,
    RunRuntimeWaitType,
)


@dataclass(frozen=True)
class CliRunAdapter:
    invoker: CliInvoker = field(default_factory=CliInvoker)

    def run(self, raw_args: str) -> RunDispatch:
        normalized_args = raw_args.strip()
        if not normalized_args:
            return _dispatch_error(
                kind=RunDispatchErrorKind.INVALID_ARGS,
                message="/run requires arguments",
            )

        try:
            payload = _run_json_command(
                self.invoker,
                "run",
                *shlex.split(normalized_args),
                "--detach",
            )
            run_id = _require_text(payload, "run_id")
            status = _parse_runtime_status(payload.get("status"))
            if status is None:
                raise RuntimeError("runtime command returned invalid status")
            return RunDispatch(
                run_id=run_id,
                status=status,
                worker_pid=_require_int(payload, "worker_pid"),
                error=RunDispatchError(
                    kind=RunDispatchErrorKind.NONE,
                    message="",
                ),
            )
        except RuntimeError as exc:
            sanitized_error = _sanitize_dispatch_error(
                str(exc),
                raw_args=normalized_args,
            )
            if _is_run_not_found_dispatch_error(sanitized_error):
                return _dispatch_error(
                    kind=RunDispatchErrorKind.RUN_NOT_FOUND,
                    message=sanitized_error,
                )
            if _is_invalid_args_dispatch_error(sanitized_error):
                return _dispatch_error(
                    kind=RunDispatchErrorKind.INVALID_ARGS,
                    message=sanitized_error,
                )
            if _is_worker_start_dispatch_error(sanitized_error):
                return _dispatch_error(
                    kind=RunDispatchErrorKind.WORKER_START_FAILED,
                    message=sanitized_error,
                )
            return _dispatch_error(
                kind=RunDispatchErrorKind.RUNTIME_ERROR,
                message=sanitized_error,
            )

    def status(self, run_id: str) -> RunRuntimeStatus | None:
        try:
            payload = _run_json_command(self.invoker, "status", run_id)
        except RuntimeError:
            return None
        status = _parse_runtime_status(payload.get("status"))
        if status is None:
            return None
        return RunRuntimeStatus(
            run_id=run_id,
            status=status,
            wait_type=_parse_runtime_wait_type(payload.get("wait_type")),
            prompt=str(payload.get("prompt", "")).strip(),
            last_event_sequence=_coerce_int(payload.get("last_event_sequence")),
            last_event_type=str(payload.get("last_event_type", "")).strip().upper(),
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


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = _coerce_int(payload.get(key))
    if value is None:
        raise RuntimeError(f"runtime command returned invalid {key}")
    return value


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key, "")).strip()
    if not value:
        raise RuntimeError(f"runtime command returned missing {key}")
    return value


def _parse_runtime_status(value: object) -> RunRuntimeStatusKind | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    try:
        return RunRuntimeStatusKind(normalized)
    except ValueError:
        return None


def _parse_runtime_wait_type(value: object) -> RunRuntimeWaitType:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return RunRuntimeWaitType.NONE
    try:
        return RunRuntimeWaitType(normalized)
    except ValueError:
        return RunRuntimeWaitType.NONE


def _dispatch_error(*, kind: RunDispatchErrorKind, message: str) -> RunDispatch:
    return RunDispatch(
        run_id="",
        status=RunRuntimeStatusKind.FAILED,
        worker_pid=0,
        error=RunDispatchError(kind=kind, message=message),
    )


def _is_run_not_found_dispatch_error(error: str) -> bool:
    return error.startswith("agent not found") or error.startswith("Invalid skill format")


def _is_invalid_args_dispatch_error(error: str) -> bool:
    return error.startswith("Invalid --arg") or error.startswith("Use either ")


def _is_worker_start_dispatch_error(error: str) -> bool:
    return "worker" in error.lower() and (
        "start" in error.lower()
        or "spawn" in error.lower()
        or "process" in error.lower()
    )


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
