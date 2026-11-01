from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from stui.adapter.cli_invoker import CliInvoker
from stui.port.installation_state_port import (
    InstallationError,
    InstallationErrorKind,
    InstallationState,
)


@dataclass(frozen=True)
class DefaultInstallationStatePort:
    invoker: CliInvoker

    def read(self) -> InstallationState:
        try:
            completed = self.invoker.run("config")
        except OSError as exc:
            return _failure(InstallationErrorKind.COMMAND_FAILED, str(exc))

        if completed.returncode != 0:
            return _failure(
                InstallationErrorKind.COMMAND_FAILED,
                _command_error(completed.stdout, completed.stderr),
            )

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return _failure(InstallationErrorKind.INVALID_RESPONSE, "Invalid config JSON response")

        runtime = payload.get("runtime") if isinstance(payload, dict) else None
        db_path = runtime.get("db_path") if isinstance(runtime, dict) else None
        if not isinstance(db_path, str) or not db_path.strip() or not Path(db_path).is_absolute():
            return _failure(
                InstallationErrorKind.INVALID_RESPONSE,
                "Config response requires an absolute runtime.db_path",
            )

        return InstallationState(runtime_db_exists=Path(db_path).exists())


def _command_error(stdout: str, stderr: str) -> str:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return stderr.strip() or stdout.strip() or "Runtime config command failed"
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if isinstance(message, str) and message.strip():
        return message
    return stderr.strip() or stdout.strip() or "Runtime config command failed"


def _failure(kind: InstallationErrorKind, message: str) -> InstallationState:
    return InstallationState(
        runtime_db_exists=False,
        error=InstallationError(kind=kind, message=message),
    )
