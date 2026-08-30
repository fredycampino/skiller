from dataclasses import dataclass
from enum import Enum
from typing import Any


class RunErrorCode(str, Enum):
    ARGUMENT_INVALID = "RUN_ARGUMENT_INVALID"
    CREATE_FAILED = "RUN_CREATE_FAILED"
    FLOW_NOT_FOUND = "FLOW_NOT_FOUND"
    INITIALIZATION_FAILED = "RUNTIME_INITIALIZATION_FAILED"
    WEBHOOK_WAIT_CONFLICT = "WEBHOOK_WAIT_CONFLICT"
    WORKER_START_FAILED = "WORKER_START_FAILED"
    WATCH_FAILED = "RUN_WATCH_FAILED"
    LOGS_FAILED = "RUN_LOGS_FAILED"
    EXECUTION_FAILED = "RUN_EXECUTION_FAILED"


@dataclass(frozen=True)
class RunCommandError:
    code: RunErrorCode
    message: str


@dataclass(frozen=True)
class RunCommandRequest:
    skill_ref: str
    skill_source: str
    inputs: dict[str, str]


@dataclass(frozen=True)
class RunCommandFailure:
    error: RunCommandError
    run_result: dict[str, Any] | None


@dataclass(frozen=True)
class RunCommandWatchResult:
    run_result: dict[str, Any]
    events: tuple[dict[str, Any], ...]


class RunOutputMapper:
    def to_error_dict(
        self,
        error: RunCommandError,
        *,
        run_result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = {} if run_result is None else dict(run_result)
        payload["error"] = {
            "code": error.code.value,
            "message": error.message,
        }
        return payload
