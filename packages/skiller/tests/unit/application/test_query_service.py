from types import SimpleNamespace

import pytest
from skiller.application.query_service import RunQueryService

pytestmark = pytest.mark.unit


class _FakeGetRunStatusUseCase:
    def execute(self, run_id: str):  # noqa: ANN201
        return SimpleNamespace(
            to_dict=lambda: {
                "id": run_id,
                "status": "WAITING",
                "current": "ask_user",
            }
        )


class _FakeGetWaitingMetadataUseCase:
    def execute(self, run_id: str):  # noqa: ANN201
        return {"prompt": f"prompt for {run_id}"}


class _FakeGetRunLogsUseCase:
    def execute(self, run_id: str) -> list[dict[str, object]]:
        return [
            {
                "sequence": 10,
                "id": "evt-1",
                "type": "STEP_SUCCESS",
                "payload": {"step": "agent"},
            },
            {
                "sequence": 11,
                "id": "evt-2",
                "type": "RUN_WAITING",
                "payload": {"step": "ask_user"},
            },
        ]

    def latest(self, run_id: str) -> dict[str, object]:
        return self.execute(run_id)[-1]


class _UnusedUseCase:
    def execute(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        raise AssertionError("unexpected use case call")


def test_query_service_status_includes_last_event_cursor() -> None:
    service = RunQueryService(
        get_execution_output_use_case=_UnusedUseCase(),
        get_run_status_use_case=_FakeGetRunStatusUseCase(),
        get_run_logs_use_case=_FakeGetRunLogsUseCase(),
        get_runs_use_case=_UnusedUseCase(),
        get_waiting_metadata_use_case=_FakeGetWaitingMetadataUseCase(),
    )

    status = service.get_status("run-1")

    assert status == {
        "id": "run-1",
        "status": "WAITING",
        "current": "ask_user",
        "prompt": "prompt for run-1",
        "last_event_sequence": 11,
        "last_event_type": "RUN_WAITING",
    }
