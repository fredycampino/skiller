from __future__ import annotations

import pytest

from stui.port.run_port import (
    RunRuntimeStatus,
    RunRuntimeStatusKind,
    RunRuntimeWaitType,
)
from stui.usecase.run_event_context import RunStatus
from stui.viewmodel.port_to_viewmodel import to_run_status

pytestmark = pytest.mark.unit


def test_to_run_status_maps_waiting_input() -> None:
    status = to_run_status(
        RunRuntimeStatus(
            run_id="run-1234",
            status=RunRuntimeStatusKind.WAITING,
            wait_type=RunRuntimeWaitType.INPUT,
        )
    )

    assert status == RunStatus.WAITING_INPUT


def test_to_run_status_maps_waiting_channel() -> None:
    status = to_run_status(
        RunRuntimeStatus(
            run_id="run-1234",
            status=RunRuntimeStatusKind.WAITING,
            wait_type=RunRuntimeWaitType.CHANNEL,
        )
    )

    assert status == RunStatus.WAITING_CHANNEL


def test_to_run_status_maps_terminal_statuses() -> None:
    succeeded = to_run_status(
        RunRuntimeStatus(run_id="run-1", status=RunRuntimeStatusKind.SUCCEEDED)
    )
    failed = to_run_status(
        RunRuntimeStatus(run_id="run-2", status=RunRuntimeStatusKind.CANCELLED)
    )

    assert succeeded == RunStatus.SUCCESS
    assert failed == RunStatus.FAILED
