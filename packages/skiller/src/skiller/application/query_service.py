from typing import Any

from skiller.application.use_cases.query.get_run_logs import GetRunLogsUseCase
from skiller.application.use_cases.query.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.query.get_runs import GetRunsUseCase
from skiller.application.use_cases.query.get_waiting_metadata import (
    GetWaitingMetadataUseCase,
)
from skiller.application.waits.waiting_metadata_mapper import WaitingMetadataMapper
from skiller.domain.run.run_status_runtime_model import RunStatusRuntime


class RunQueryService:
    def __init__(
        self,
        get_run_status_use_case: GetRunStatusUseCase,
        get_run_logs_use_case: GetRunLogsUseCase,
        get_runs_use_case: GetRunsUseCase,
        get_waiting_metadata_use_case: GetWaitingMetadataUseCase,
        waiting_metadata_mapper: WaitingMetadataMapper,
    ) -> None:
        self.get_run_status_use_case = get_run_status_use_case
        self.get_run_logs_use_case = get_run_logs_use_case
        self.get_runs_use_case = get_runs_use_case
        self.get_waiting_metadata_use_case = get_waiting_metadata_use_case
        self.waiting_metadata_mapper = waiting_metadata_mapper

    def get_status(self, run_id: str) -> RunStatusRuntime | None:
        status = self.get_run_status_use_case.execute(run_id)
        if status is None:
            return None

        waiting_metadata = self.get_waiting_metadata_use_case.execute(run_id)
        last_event = self.get_run_logs_use_case.latest(run_id)
        waiting_status = self.waiting_metadata_mapper.to_status(waiting_metadata)

        last_event_sequence = None
        last_event_type = None
        if last_event is not None:
            last_event_sequence = last_event.sequence
            last_event_type = last_event.type

        return RunStatusRuntime(
            run_id=status.run_id,
            status=status.status,
            wait_type=waiting_status.wait_type,
            prompt=waiting_status.prompt,
            last_event_sequence=last_event_sequence,
            last_event_type=last_event_type,
        )

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
