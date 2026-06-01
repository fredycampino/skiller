import pytest

from skiller.application.query_service import RunQueryService
from skiller.domain.event.event_model import (
    RuntimeEvent,
    RuntimeEventType,
    RunWaitingPayload,
    StepSuccessPayload,
)
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_status_runtime_model import RunStatusRuntime

pytestmark = pytest.mark.unit


class _FakeGetRunStatusUseCase:
    def execute(self, run_id: str):  # noqa: ANN201
        return RunStatusRuntime(
            run_id=run_id,
            status=RunStatus.WAITING,
        )


class _FakeGetWaitingMetadataUseCase:
    def execute(self, run_id: str):  # noqa: ANN201
        return {"wait_type": "input", "prompt": f"prompt for {run_id}"}


class _FakeGetRunLogsUseCase:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def execute(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[RuntimeEvent]:
        self.calls.append(
            {
                "run_id": run_id,
                "after_sequence": after_sequence,
                "limit": limit,
            }
        )
        return [
            RuntimeEvent(
                sequence=10,
                id="evt-1",
                run_id=run_id,
                type=RuntimeEventType.STEP_SUCCESS,
                step_id="agent",
                step_type="agent",
                agent_sequence=None,
                created_at="2026-05-12 10:00:00",
                payload=StepSuccessPayload(output={}),
            ),
            RuntimeEvent(
                sequence=11,
                id="evt-2",
                run_id=run_id,
                type=RuntimeEventType.RUN_WAITING,
                step_id="ask_user",
                step_type="wait_input",
                agent_sequence=None,
                created_at="2026-05-12 10:00:01",
                payload=RunWaitingPayload(output={}),
            ),
        ]

    def latest(self, run_id: str) -> RuntimeEvent:
        return self.execute(run_id)[-1]


class _UnusedUseCase:
    def execute(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        raise AssertionError("unexpected use case call")


def test_query_service_status_includes_last_event_cursor() -> None:
    service = RunQueryService(
        get_run_status_use_case=_FakeGetRunStatusUseCase(),
        get_run_logs_use_case=_FakeGetRunLogsUseCase(),
        get_runs_use_case=_UnusedUseCase(),
        get_waiting_metadata_use_case=_FakeGetWaitingMetadataUseCase(),
    )

    status = service.get_status("run-1")

    assert status == (
        RunStatusRuntime(
            run_id="run-1",
            status=RunStatus.WAITING,
            wait_type="input",
            prompt="prompt for run-1",
            last_event_sequence=11,
            last_event_type=RuntimeEventType.RUN_WAITING,
        )
    )


def test_query_service_logs_returns_public_json() -> None:
    get_logs = _FakeGetRunLogsUseCase()
    service = RunQueryService(
        get_run_status_use_case=_UnusedUseCase(),
        get_run_logs_use_case=get_logs,
        get_runs_use_case=_UnusedUseCase(),
        get_waiting_metadata_use_case=_UnusedUseCase(),
    )

    logs = service.get_logs("run-1", after_sequence=10, limit=50)

    assert get_logs.calls == [
        {
            "run_id": "run-1",
            "after_sequence": 10,
            "limit": 50,
        }
    ]

    assert logs == [
        {
            "sequence": 10,
            "id": "evt-1",
            "run_id": "run-1",
            "type": "STEP_SUCCESS",
            "created_at": "2026-05-12 10:00:00",
            "step_id": "agent",
            "step_type": "agent",
            "agent_sequence": None,
            "payload": {"output": {}},
        },
        {
            "sequence": 11,
            "id": "evt-2",
            "run_id": "run-1",
            "type": "RUN_WAITING",
            "created_at": "2026-05-12 10:00:01",
            "step_id": "ask_user",
            "step_type": "wait_input",
            "agent_sequence": None,
            "payload": {
                "output": {},
            },
        },
    ]
