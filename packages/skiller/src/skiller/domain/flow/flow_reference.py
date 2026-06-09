from typing import Protocol


class FlowReference(Protocol):
    source: str
    ref: str
