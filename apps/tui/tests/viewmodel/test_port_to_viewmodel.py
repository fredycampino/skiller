from __future__ import annotations

import pytest

from stui.port.run_port import (
    RunRuntimeStatus,
    RunRuntimeStatusKind,
    RunRuntimeWaitType,
)
from stui.usecase.run_event_context import RunMode, RunStatus
from stui.viewmodel.port_to_viewmodel import run_runtime_status_to_event_context

pytestmark = pytest.mark.unit


def test_run_runtime_status_to_event_context_maps_waiting_input() -> None:
    context = run_runtime_status_to_event_context(
        RunRuntimeStatus(
            run_id="run-1234",
            status=RunRuntimeStatusKind.WAITING,
            wait_type=RunRuntimeWaitType.INPUT,
        ),
        skill_name="ant",
        mode=RunMode.CHAT,
    )

    assert context.run_id == "run-1234"
    assert context.skill_name == "ant"
    assert context.mode == RunMode.CHAT
    assert context.status == RunStatus.WAITING_INPUT


def test_run_runtime_status_to_event_context_maps_waiting_channel() -> None:
    context = run_runtime_status_to_event_context(
        RunRuntimeStatus(
            run_id="run-1234",
            status=RunRuntimeStatusKind.WAITING,
            wait_type=RunRuntimeWaitType.CHANNEL,
        ),
        skill_name="ant",
        mode=RunMode.FLOW,
    )

    assert context.status == RunStatus.WAITING_CHANNEL


def test_run_runtime_status_to_event_context_maps_terminal_statuses() -> None:
    succeeded = run_runtime_status_to_event_context(
        RunRuntimeStatus(run_id="run-1", status=RunRuntimeStatusKind.SUCCEEDED),
        skill_name="ant",
        mode=RunMode.FLOW,
    )
    failed = run_runtime_status_to_event_context(
        RunRuntimeStatus(run_id="run-2", status=RunRuntimeStatusKind.CANCELLED),
        skill_name="ant",
        mode=RunMode.FLOW,
    )

    assert succeeded.status == RunStatus.SUCCESS
    assert failed.status == RunStatus.FAILED
