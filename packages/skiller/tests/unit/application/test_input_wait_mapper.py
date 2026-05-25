import pytest

from skiller.application.use_cases.ingress.handle_input import HandleInputResult
from skiller.application.waits.input_mapper import InputWaitMapper

pytestmark = pytest.mark.unit


def test_mapper_builds_handle_input_and_output() -> None:
    mapper = InputWaitMapper()

    request = mapper.to_handle_input(" run-1 ", text=" hello ")
    result = HandleInputResult(
        accepted=True,
        run_ids=["run-1"],
    )

    assert request.run_id == "run-1"
    assert request.text == "hello"
    assert mapper.to_handle_dict(request, result) == {
        "accepted": True,
        "run_id": "run-1",
        "matched_runs": ["run-1"],
    }
