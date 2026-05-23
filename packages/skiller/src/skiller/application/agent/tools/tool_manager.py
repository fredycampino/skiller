from dataclasses import dataclass
from enum import Enum

from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.domain.tool.tool_contract import (
    ConfiguredTool,
    Tool,
    ToolDefinition,
    ToolInput,
    ToolPolicy,
    ToolPolicyResult,
    ToolRequest,
    ToolResult,
    ToolResultStatus,
    ToolRuntimeConfig,
)


@dataclass(frozen=True)
class PreparedTool:
    name: str
    tool: ToolDefinition
    request: ToolRequest
    config: ToolRuntimeConfig | None


class ToolPrepareFailure(str, Enum):
    REQUEST_INVALID = "request_invalid"
    REQUEST_EXCEPTION = "request_exception"
    POLICY_BLOCKED = "policy_blocked"
    POLICY_EXCEPTION = "policy_exception"


@dataclass(frozen=True)
class ToolPrepareResult:
    ok: bool
    tool_name: str
    prepared: PreparedTool | None = None
    error: ToolPrepareFailure | None = None
    error_message: str | None = None


class ToolManager:
    def __init__(
        self,
        tools: list[ToolDefinition],
    ) -> None:
        self._tools_by_name: dict[str, ToolDefinition] = {}

        for tool in tools:
            if tool.name in self._tools_by_name:
                raise ValueError(f"Agent tool '{tool.name}' is configured more than once")

            self._tools_by_name[tool.name] = tool

    def get_tools(self, allowed_tools: list[str]) -> list[ToolDefinition]:
        resolved: list[ToolDefinition] = []
        for tool_type in allowed_tools:
            resolved.append(self._get_tool(tool_type))
        return resolved

    def get_tool_definitions(self, allowed_tools: list[str]) -> list[ToolDefinition]:
        resolved: list[ToolDefinition] = []
        for tool_type in allowed_tools:
            resolved.append(self._get_tool(tool_type))
        return resolved

    def prepare(self, request: AgentToolRequest) -> ToolPrepareResult:
        if request.tool not in request.allowed_tools:
            return ToolPrepareResult(
                ok=False,
                tool_name=request.tool,
                error=ToolPrepareFailure.REQUEST_INVALID,
                error_message=f"Tool '{request.tool}' is not allowed in this step",
            )

        tool = self._tools_by_name.get(request.tool)
        if tool is None:
            return ToolPrepareResult(
                ok=False,
                tool_name=request.tool,
                error=ToolPrepareFailure.REQUEST_INVALID,
                error_message=f"Tool '{request.tool}' is not configured",
            )
        runtime_config = request.runtime_config
        if runtime_config is not None and runtime_config.definition.name != request.tool:
            return ToolPrepareResult(
                ok=False,
                tool_name=request.tool,
                error=ToolPrepareFailure.REQUEST_INVALID,
                error_message=f"Tool '{request.tool}' received mismatched runtime config",
            )
        if isinstance(tool, ConfiguredTool) and runtime_config is None:
            return ToolPrepareResult(
                ok=False,
                tool_name=request.tool,
                error=ToolPrepareFailure.REQUEST_INVALID,
                error_message=f"Tool '{request.tool}' requires runtime config",
            )

        try:
            request_result = tool.request(
                ToolInput(
                    run_id=request.run_id,
                    step_id=request.step_id,
                    tool_call_id=request.tool_call_id,
                    args=request.args,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return ToolPrepareResult(
                ok=False,
                tool_name=request.tool,
                error=ToolPrepareFailure.REQUEST_EXCEPTION,
                error_message=str(exc).strip(),
            )
        if not request_result.ok:
            return ToolPrepareResult(
                ok=False,
                tool_name=request.tool,
                error=ToolPrepareFailure.REQUEST_INVALID,
                error_message=request_result.error,
            )
        if request_result.request is None:
            return ToolPrepareResult(
                ok=False,
                tool_name=request.tool,
                error=ToolPrepareFailure.REQUEST_EXCEPTION,
                error_message=f"Tool '{request.tool}' request returned no request",
            )
        typed_request = request_result.request

        try:
            if isinstance(tool, ToolPolicy):
                policy_result = tool.policy(
                    config=runtime_config,
                    request=typed_request,
                )
            else:
                policy_result = ToolPolicyResult.allowed(typed_request)
        except Exception as exc:  # noqa: BLE001
            return ToolPrepareResult(
                ok=False,
                tool_name=request.tool,
                error=ToolPrepareFailure.POLICY_EXCEPTION,
                error_message=str(exc).strip(),
            )
        if not policy_result.ok:
            return ToolPrepareResult(
                ok=False,
                tool_name=request.tool,
                error=ToolPrepareFailure.POLICY_BLOCKED,
                error_message=policy_result.error,
            )
        if policy_result.request is None:
            return ToolPrepareResult(
                ok=False,
                tool_name=request.tool,
                error=ToolPrepareFailure.POLICY_EXCEPTION,
                error_message=f"Tool '{request.tool}' policy returned no request",
            )

        return ToolPrepareResult(
            ok=True,
            tool_name=request.tool,
            prepared=PreparedTool(
                name=request.tool,
                tool=tool,
                request=policy_result.request,
                config=runtime_config,
            ),
        )

    def execute_prepared(self, prepared: PreparedTool) -> ToolResult:
        try:
            if not isinstance(prepared.tool, Tool):
                raise ValueError(
                    f"Agent tool '{prepared.name}' does not support direct execution"
                )
            typed_result = prepared.tool.run(
                config=prepared.config,
                request=prepared.request,
            )
            if not isinstance(typed_result, ToolResult):
                raise ValueError(f"Agent tool '{prepared.name}' returned invalid result")
            if typed_result.name != prepared.name:
                raise ValueError(
                    f"Agent tool '{prepared.name}' returned mismatched result name"
                )
            return typed_result
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                name=prepared.name,
                status=ToolResultStatus.FAILED,
                data={},
                text=None,
                error=str(exc).strip() or f"Agent tool '{prepared.name}' failed",
            )

    def _get_tool(self, tool_name: str) -> ToolDefinition:
        tool = self._tools_by_name.get(tool_name)
        if tool is None:
            raise ValueError(f"Agent tool '{tool_name}' is not configured")
        return tool
