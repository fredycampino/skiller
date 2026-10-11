from pathlib import Path
from typing import Any, Protocol

from skiller.domain.flow.flow_run_reference import FlowRunReference


class RunnerPort(Protocol):
    def load(self, flow_path: Path) -> dict[str, Any]: ...

    def render(
        self,
        step: dict[str, Any],
        context: dict[str, Any],
        *,
        flow: FlowRunReference,
    ) -> dict[str, Any]: ...

    def read_instruction(self, flow_path: Path, reference: str) -> str: ...

    def read_system_file(self, flow_path: Path, file_ref: str) -> str: ...

    def read_file(
        self,
        flow_path: Path,
        file_ref: str,
    ) -> str: ...

    def resolve_file_path(
        self,
        flow_path: Path,
        file_ref: str,
    ) -> Path: ...

    def resolve_flow_dir(self, flow_path: Path) -> Path: ...
