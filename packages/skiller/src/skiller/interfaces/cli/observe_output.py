from __future__ import annotations

import json
from typing import TextIO


class ObserveOutputClosed(Exception):
    pass


class JsonlFrameWriter:
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream

    def write(self, frame: dict[str, object]) -> None:
        line = json.dumps(frame, ensure_ascii=False, separators=(",", ":"))
        try:
            self.stream.write(f"{line}\n")
            self.stream.flush()
        except BrokenPipeError as exc:
            raise ObserveOutputClosed from exc
