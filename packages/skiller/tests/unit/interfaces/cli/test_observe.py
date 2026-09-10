import io
import json

import pytest

from skiller.interfaces.cli.observe import ObserveCommand
from skiller.interfaces.cli.observe_output import JsonlFrameWriter

pytestmark = pytest.mark.unit


class _FakeCancellation:
    def __init__(self, *, stop_after_wait: bool = False) -> None:
        self._requested = False
        self.stop_after_wait = stop_after_wait
        self.wait_calls: list[float] = []

    @property
    def requested(self) -> bool:
        return self._requested

    def wait(self, timeout_seconds: float) -> bool:
        self.wait_calls.append(timeout_seconds)
        if self.stop_after_wait:
            self._requested = True
        return self._requested


class _FailOnAdditionalRead:
    def __init__(self) -> None:
        self.reads = 0

    def __iter__(self):  # noqa: ANN201
        return self

    def __next__(self) -> dict[str, object] | None:
        self.reads += 1
        if self.reads == 1:
            return {"kind": "start"}
        if self.reads == 2:
            return None
        raise AssertionError("stream was consumed after cancellation")


def test_command_writes_frames_and_waits_only_for_idle_results() -> None:
    output = io.StringIO()
    cancellation = _FakeCancellation()
    stream = iter(
        [
            {"kind": "start"},
            {"kind": "event", "event": {"sequence": 1}},
            None,
            {"kind": "stop"},
        ]
    )
    command = ObserveCommand(
        writer=JsonlFrameWriter(output),
        cancellation=cancellation,
        poll_interval_seconds=2.5,
    )

    exit_code = command.execute(stream)

    assert exit_code == 0
    assert [json.loads(line) for line in output.getvalue().splitlines()] == [
        {"kind": "start"},
        {"kind": "event", "event": {"sequence": 1}},
        {"kind": "stop"},
    ]
    assert cancellation.wait_calls == [2.5]


def test_command_stops_consuming_after_cancellation() -> None:
    output = io.StringIO()
    cancellation = _FakeCancellation(stop_after_wait=True)
    stream = _FailOnAdditionalRead()
    command = ObserveCommand(
        writer=JsonlFrameWriter(output),
        cancellation=cancellation,
    )

    exit_code = command.execute(stream)

    assert exit_code == 0
    assert [json.loads(line) for line in output.getvalue().splitlines()] == [{"kind": "start"}]
    assert stream.reads == 2
