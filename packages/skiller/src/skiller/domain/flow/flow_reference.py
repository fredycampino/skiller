from typing import Protocol


class FlowReference(Protocol):
    id: str
    source: str
    ref: str
