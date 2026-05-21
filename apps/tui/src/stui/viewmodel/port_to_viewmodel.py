from __future__ import annotations

from stui.port.run_port import (
    RunRuntimeStatus,
    RunRuntimeStatusKind,
    RunRuntimeWaitType,
)
from stui.usecase.run_event_context import RunStatus


def to_run_status(runtime_status: RunRuntimeStatus) -> RunStatus:
    if runtime_status.status == RunRuntimeStatusKind.WAITING:
        if runtime_status.wait_type == RunRuntimeWaitType.INPUT:
            return RunStatus.WAITING_INPUT
        if runtime_status.wait_type == RunRuntimeWaitType.CHANNEL:
            return RunStatus.WAITING_CHANNEL
        return RunStatus.WAITING_WEBHOOK
    if runtime_status.status == RunRuntimeStatusKind.SUCCEEDED:
        return RunStatus.SUCCESS
    if runtime_status.status in {
        RunRuntimeStatusKind.FAILED,
        RunRuntimeStatusKind.CANCELLED,
    }:
        return RunStatus.FAILED
    return RunStatus.RUNNING
