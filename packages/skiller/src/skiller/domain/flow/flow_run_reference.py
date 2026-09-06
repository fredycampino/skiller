from pathlib import Path
from typing import Protocol


class FlowRunReference(Protocol):
    id: str
    flow_path: Path
