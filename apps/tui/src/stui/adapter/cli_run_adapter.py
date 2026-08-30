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
            args = shlex.split(normalized_args)
            command_args = ("run", *args, "--detach")
            if args and _looks_like_skill_file(args[0]):
                command_args = ("run", "--file", *args, "--detach")
            completed = self.invoker.run(*command_args)
            if completed.returncode != 0:
                return _dispatch_error_from_payload(_parse_error_payload(completed.stdout))
            payload = _parse_success_payload(completed.stdout)
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
            return _dispatch_error(
                kind=RunDispatchErrorKind.RUNTIME_ERROR,
                message=str(exc),
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
        raise RuntimeError("runtime command failed")
    return _parse_success_payload(completed.stdout)


def _parse_success_payload(stdout: str) -> dict[str, Any]:
    payload = _parse_json_object(stdout)
    if "error" in payload:
        raise RuntimeError("runtime command returned an error payload")
    return payload


def _parse_error_payload(stdout: str) -> tuple[str, str]:
    payload = _parse_json_object(stdout)
    error = payload.get("error")
    if not isinstance(error, dict):
        raise RuntimeError("runtime command returned invalid error payload")
    code = _require_text(error, "code")
    message = _require_text(error, "message")
    return code, message


def _parse_json_object(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("runtime command returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("runtime command returned invalid payload")
    return payload


def _dispatch_error_from_payload(error: tuple[str, str]) -> RunDispatch:
    code, message = error
    kinds = {
        "RUN_ARGUMENT_INVALID": RunDispatchErrorKind.INVALID_ARGS,
        "FLOW_NOT_FOUND": RunDispatchErrorKind.FLOW_NOT_FOUND,
        "WEBHOOK_WAIT_CONFLICT": RunDispatchErrorKind.WEBHOOK_WAIT_CONFLICT,
        "WORKER_START_FAILED": RunDispatchErrorKind.WORKER_START_FAILED,
        "RUNTIME_INITIALIZATION_FAILED": RunDispatchErrorKind.INITIALIZATION_FAILED,
        "RUN_CREATE_FAILED": RunDispatchErrorKind.CREATE_FAILED,
    }
    return _dispatch_error(
        kind=kinds.get(code, RunDispatchErrorKind.RUNTIME_ERROR), message=message
    )


def _looks_like_skill_file(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized.endswith(".yaml") or normalized.endswith(".yml")


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
