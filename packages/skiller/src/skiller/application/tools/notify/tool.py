from dataclasses import dataclass
from typing import ClassVar

from skiller.domain.tool.tool_contract import (
    Tool,
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolResult,
    ToolResultStatus,
    ToolRuntimeConfig,
    ToolSchema,
)


@dataclass(frozen=True)
class NotifyToolRequest(ToolRequest):
    message: str


class NotifyTool(ToolDefinition[NotifyToolRequest], Tool[NotifyToolRequest]):
    name: ClassVar[str] = "notify"
    description: ClassVar[str] = "Send a notification message to the active channel"

    def schema(self) -> ToolSchema:
        return ToolSchema(
            value={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                },
                "required": ["message"],
                "additionalProperties": False,
            }
        )

    def request(self, input: ToolInput) -> ToolRequestResult[NotifyToolRequest]:
        try:
            return ToolRequestResult.valid(
                NotifyToolRequest(message=input.require_string("message"))
            )
        except ValueError as exc:
            return ToolRequestResult.invalid(str(exc))

    def run(
        self,
        *,
        config: ToolRuntimeConfig | None,
        request: NotifyToolRequest,
    ) -> ToolResult:
        return ToolResult(
            name=self.name,
            status=ToolResultStatus.COMPLETED,
            data={"message": request.message},
            text=request.message,
            error=None,
        )
