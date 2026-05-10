from typing import Protocol

from skiller.domain.tool.tool_process_model import (
    ToolProcessHandle,
    ToolProcessOutput,
    ToolProcessRequest,
    ToolProcessWait,
    ToolProcessWaitResult,
)


class ToolProcessPort(Protocol):
    def popen(self, request: ToolProcessRequest) -> ToolProcessHandle: ...

    def write(self, handle: ToolProcessHandle, payload: str) -> None: ...

    def poll(self, handle: ToolProcessHandle) -> int | None: ...

    def read(self, handle: ToolProcessHandle) -> ToolProcessOutput: ...

    def terminate(self, handle: ToolProcessHandle) -> None: ...

    def wait(
        self,
        request: ToolProcessWait,
    ) -> ToolProcessWaitResult: ...
