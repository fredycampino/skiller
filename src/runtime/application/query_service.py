from typing import Any

from runtime.application.use_cases.get_run_logs import GetRunLogsUseCase
from runtime.application.use_cases.get_run_status import GetRunStatusUseCase


class RunQueryService:
    def __init__(
        self,
        get_run_status_use_case: GetRunStatusUseCase,
        get_run_logs_use_case: GetRunLogsUseCase,
    ) -> None:
        self.get_run_status_use_case = get_run_status_use_case
        self.get_run_logs_use_case = get_run_logs_use_case

    def get_status(self, run_id: str) -> dict[str, Any] | None:
        return self.get_run_status_use_case.execute(run_id)

    def get_logs(self, run_id: str) -> list[dict[str, Any]]:
        return self.get_run_logs_use_case.execute(run_id)
