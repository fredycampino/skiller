from pathlib import Path
from typing import Protocol


class PackagedFlowPathsPort(Protocol):
    def get_paths(self) -> tuple[Path, ...]: ...
