from typing import Any

from skiller.application.use_cases.get_execution_output import GetExecutionOutputUseCase
from skiller.application.use_cases.get_run_logs import GetRunLogsUseCase
from skiller.application.use_cases.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.get_runs import GetRunsUseCase
from skiller.application.use_cases.get_waiting_metadata import GetWaitingMetadataUseCase


class RunQueryService:
    def __init__(
        self,
        get_execution_output_use_case: GetExecutionOutputUseCase,
        get_run_status_use_case: GetRunStatusUseCase,
        get_run_logs_use_case: GetRunLogsUseCase,
        get_runs_use_case: GetRunsUseCase,
        get_waiting_metadata_use_case: GetWaitingMetadataUseCase,
    ) -> None:
        self.get_execution_output_use_case = get_execution_output_use_case
        self.get_run_status_use_case = get_run_status_use_case
        self.get_run_logs_use_case = get_run_logs_use_case
        self.get_runs_use_case = get_runs_use_case
        self.get_waiting_metadata_use_case = get_waiting_metadata_use_case

    def get_status(self, run_id: str) -> dict[str, Any] | None:
        run = self.get_run_status_use_case.execute(run_id)
        if run is None:
            return None
        payload = run.to_dict()
        waiting_metadata = self.get_waiting_metadata_use_case.execute(run_id)
        if waiting_metadata is not None:
            payload.update(waiting_metadata)
        return payload

    def get_logs(self, run_id: str) -> list[dict[str, Any]]:
        return self.get_run_logs_use_case.execute(run_id)

    def get_execution_output(self, body_ref: str) -> dict[str, Any] | None:
        return self.get_execution_output_use_case.execute(body_ref)

    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        runs = self.get_runs_use_case.execute(limit=limit, statuses=statuses)
        return [run.to_dict() for run in runs]
