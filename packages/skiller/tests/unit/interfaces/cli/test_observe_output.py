import io
import json

import pytest

from skiller.interfaces.cli.observe_output import JsonlFrameWriter, ObserveOutputClosed

pytestmark = pytest.mark.unit


class _FlushTrackingStream(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_calls = 0

    def flush(self) -> None:
        self.flush_calls += 1
        super().flush()


class _ClosedPipe:
    def write(self, _value: str) -> int:
        raise BrokenPipeError

    def flush(self) -> None:
        raise AssertionError("flush must not run after a failed write")


def test_jsonl_writer_writes_one_compact_line_and_flushes() -> None:
    stream = _FlushTrackingStream()
    writer = JsonlFrameWriter(stream)

    writer.write({"kind": "event", "event": {"text": "á"}})

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"kind": "event", "event": {"text": "á"}}
    assert stream.flush_calls == 1


def test_jsonl_writer_maps_broken_pipe_to_normal_output_close() -> None:
    writer = JsonlFrameWriter(_ClosedPipe())  # type: ignore[arg-type]

    with pytest.raises(ObserveOutputClosed):
        writer.write({"kind": "start"})
