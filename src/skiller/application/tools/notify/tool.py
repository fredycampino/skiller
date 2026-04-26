from dataclasses import dataclass

from skiller.domain.tool.tool_contract import Tool, ToolRequest, ToolResult, ToolResultStatus


@dataclass(frozen=True)
class NotifyToolRequest(ToolRequest):
    message: str


class NotifyTool(Tool[NotifyToolRequest, ToolResult]):
    name = "notify"

    def execute(self, request: NotifyToolRequest) -> ToolResult:
        return ToolResult(
            name=self.name,
            status=ToolResultStatus.COMPLETED,
            data={"message": request.message},
            text=request.message,
            error=None,
        )
