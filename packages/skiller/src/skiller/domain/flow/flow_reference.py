from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FlowReference:
    value: str


@dataclass(frozen=True)
class ResolvedFlow:
    reference: FlowReference
    flow_path: Path
