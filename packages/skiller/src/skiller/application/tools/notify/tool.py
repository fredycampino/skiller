from dataclasses import dataclass

from skiller.application.tools.notify.config import NotifyToolConfig
from skiller.domain.tool.tool_contract import (
    Tool,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolResult,
    ToolResultStatus,
)


@dataclass(frozen=True)
class NotifyToolRequest(ToolRequest):
    message: str


class NotifyTool(Tool[NotifyToolRequest]):
    name = "notify"
    config = NotifyToolConfig()

    def request(self, input: ToolInput) -> ToolRequestResult[NotifyToolRequest]:
        try:
            return ToolRequestResult.valid(
                NotifyToolRequest(message=input.require_string("message"))
            )
        except ValueError as exc:
            return ToolRequestResult.invalid(str(exc))

    def run(self, request: NotifyToolRequest) -> ToolResult:
        return ToolResult(
            name=self.name,
            status=ToolResultStatus.COMPLETED,
            data={"message": request.message},
            text=request.message,
            error=None,
        )
