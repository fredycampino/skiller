from pathlib import Path
from typing import Any, Protocol

from skiller.domain.flow.flow_reference import FlowReference


class RunnerPort(Protocol):
    def load(self, source: str, ref: str) -> dict[str, Any]: ...

    def render(
        self,
        step: dict[str, Any],
        context: dict[str, Any],
        *,
        flow: FlowReference,
    ) -> dict[str, Any]: ...

    def read_file(
        self,
        source: str,
        ref: str,
        file_ref: str,
    ) -> str: ...

    def resolve_file_path(
        self,
        source: str,
        ref: str,
        file_ref: str,
    ) -> Path: ...
