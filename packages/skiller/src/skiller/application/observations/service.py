from collections.abc import Iterator

from skiller.application.observations.models import ObserveRunInput, ObserveRunResult
from skiller.application.use_cases.query.observe_run import ObserveRunUseCase


class ObserveRunApplicationService:
    def __init__(self, observe_run_use_case: ObserveRunUseCase) -> None:
        self.observe_run_use_case = observe_run_use_case

    def observe(self, request: ObserveRunInput) -> Iterator[ObserveRunResult]:
        return self.observe_run_use_case.execute(request)
