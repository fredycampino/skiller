from typing import Protocol

from skiller.domain.tool.tool_execution_model import (
    ToolExecutionRequest,
    ToolExecutionResults,
)


class ToolExecutionPort(Protocol):
    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResults: ...
