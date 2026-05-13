from typing import Any

from skiller.application.use_cases.query.get_run_logs import GetRunLogsUseCase
from skiller.application.use_cases.query.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.query.get_runs import GetRunsUseCase
from skiller.application.use_cases.query.get_waiting_metadata import (
    GetWaitingMetadataUseCase,
)


class RunQueryService:
    def __init__(
        self,
        get_run_status_use_case: GetRunStatusUseCase,
        get_run_logs_use_case: GetRunLogsUseCase,
        get_runs_use_case: GetRunsUseCase,
        get_waiting_metadata_use_case: GetWaitingMetadataUseCase,
    ) -> None:
        self.get_run_status_use_case = get_run_status_use_case
        self.get_run_logs_use_case = get_run_logs_use_case
        self.get_runs_use_case = get_runs_use_case
        self.get_waiting_metadata_use_case = get_waiting_metadata_use_case

    def get_status(
        self,
        run_id: str,
        *,
        include_context: bool = False,
    ) -> dict[str, Any] | None:
        run = self.get_run_status_use_case.execute(run_id)
        if run is None:
            return None
        payload = run.to_dict()
        if not include_context:
            payload.pop("context", None)
        waiting_metadata = self.get_waiting_metadata_use_case.execute(run_id)
        if waiting_metadata is not None:
            payload.update(waiting_metadata)
        last_event = self.get_run_logs_use_case.latest(run_id)
        if last_event is not None:
            payload["last_event_sequence"] = last_event.sequence
            payload["last_event_type"] = last_event.type.value
        return payload

    def get_logs(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return [
            event.model_dump(mode="json")
            for event in self.get_run_logs_use_case.execute(
                run_id,
                after_sequence=after_sequence,
                limit=limit,
            )
        ]

    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        runs = self.get_runs_use_case.execute(limit=limit, statuses=statuses)
        return [run.to_dict() for run in runs]
