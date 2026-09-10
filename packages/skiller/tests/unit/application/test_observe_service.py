import pytest

from skiller.application.observations.models import ObserveIdle, ObserveRunInput
from skiller.application.observations.service import ObserveRunApplicationService

pytestmark = pytest.mark.unit


class _FakeObserveRunUseCase:
    def __init__(self) -> None:
        self.request: ObserveRunInput | None = None

    def execute(self, request: ObserveRunInput):  # noqa: ANN201
        self.request = request
        return iter([ObserveIdle()])


def test_service_delegates_to_observe_run_use_case() -> None:
    use_case = _FakeObserveRunUseCase()
    service = ObserveRunApplicationService(use_case)  # type: ignore[arg-type]
    request = ObserveRunInput(run_id="run-1", after=None, tail=100)

    results = list(service.observe(request))

    assert use_case.request is request
    assert results == [ObserveIdle()]
