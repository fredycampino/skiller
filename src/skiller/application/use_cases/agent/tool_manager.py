from dataclasses import dataclass
from typing import Any, Protocol

from skiller.application.tools.tool_adapter import ToolAdapter
from skiller.application.use_cases.agent.tool_manager_model import AgentToolRequest
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus


class AgentTool(Protocol):
    name: str

    def execute(self, request: Any) -> Any:
        raise NotImplementedError


@dataclass(frozen=True)
class _ToolBinding:
    tool: AgentTool
    adapter: ToolAdapter[Any]


class ToolManager:
    def __init__(
        self,
        tools: list[AgentTool],
        adapters: list[ToolAdapter[Any]],
    ) -> None:
        adapters_by_name = self._build_adapters_by_name(adapters)
        self._bindings_by_name: dict[str, _ToolBinding] = {}

        for tool in tools:
            if tool.name in self._bindings_by_name:
                raise ValueError(f"Agent tool '{tool.name}' is configured more than once")

            adapter = adapters_by_name.get(tool.name)
            if adapter is None:
                raise ValueError(f"Agent tool '{tool.name}' does not have an adapter")

            self._bindings_by_name[tool.name] = _ToolBinding(
                tool=tool,
                adapter=adapter,
            )

    def get_tools(self, allowed_tools: list[str]) -> list[AgentTool]:
        resolved: list[AgentTool] = []
        for tool_type in allowed_tools:
            binding = self._bindings_by_name.get(tool_type)
            if binding is None:
                raise ValueError(f"Agent tool '{tool_type}' is not configured")
            resolved.append(binding.tool)
        return resolved

    def execute(self, request: AgentToolRequest) -> ToolResult:
        if request.tool not in request.allowed_tools:
            return ToolResult(
                name=request.tool,
                status=ToolResultStatus.FAILED,
                data={},
                text=None,
                error=f"Agent tool '{request.tool}' is not allowed in this step",
            )

        binding = self._bindings_by_name.get(request.tool)
        if binding is None:
            return ToolResult(
                name=request.tool,
                status=ToolResultStatus.FAILED,
                data={},
                text=None,
                error=f"Agent tool '{request.tool}' is not configured",
            )

        try:
            typed_request = binding.adapter.build_request(
                step_id=request.step_id,
                value=request.args,
            )
            typed_result = binding.tool.execute(typed_request)
            if not isinstance(typed_result, ToolResult):
                raise ValueError(f"Agent tool '{request.tool}' returned invalid result")
            if typed_result.name != request.tool:
                raise ValueError(f"Agent tool '{request.tool}' returned mismatched result name")
            return typed_result
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                name=request.tool,
                status=ToolResultStatus.FAILED,
                data={},
                text=None,
                error=str(exc).strip() or f"Agent tool '{request.tool}' failed",
            )

    def _build_adapters_by_name(
        self,
        adapters: list[ToolAdapter[Any]],
    ) -> dict[str, ToolAdapter[Any]]:
        adapters_by_name: dict[str, ToolAdapter[Any]] = {}
        for adapter in adapters:
            if adapter.name in adapters_by_name:
                raise ValueError(
                    f"Agent tool adapter '{adapter.name}' is configured more than once"
                )
            adapters_by_name[adapter.name] = adapter
        return adapters_by_name
