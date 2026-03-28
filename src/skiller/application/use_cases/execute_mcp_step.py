from skiller.application.ports.mcp_port import MCPPort
from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    McpResult,
    StepExecutionResult,
    StepExecutionStatus,
)
from skiller.domain.mcp_config_model import RenderedMcpConfig
from skiller.domain.run_model import RunStatus


class ExecuteMcpStepUseCase:
    def __init__(self, store: StateStorePort, mcp: MCPPort) -> None:
        self.store = store
        self.mcp = mcp

    def execute(
        self, current_step: CurrentStep, mcp_config: RenderedMcpConfig
    ) -> StepExecutionResult:
        step_id = current_step.step_id
        step = current_step.step
        context = current_step.context

        server_name = str(step.get("mcp", "")).strip()
        tool_name = str(step.get("tool", "")).strip()
        args = step.get("args", {})

        if not server_name:
            raise ValueError(f"Step '{step_id}' requires mcp server name in field 'mcp'")
        if not tool_name:
            raise ValueError(f"Step '{step_id}' requires tool name in field 'tool'")
        if tool_name.startswith("mcp."):
            raise ValueError(
                f"Step '{step_id}' invalid tool '{tool_name}'. "
                "For type 'mcp', use plain tool name without "
                "'mcp.<server>.' prefix."
            )
        if not isinstance(args, dict):
            raise ValueError(f"Step '{step_id}' args must be an object")

        result = self.mcp.call_tool(server_name, tool_name, args, config=mcp_config)
        context.results[step_id] = result

        if result.get("ok") is False:
            error = str(result.get("error", "")).strip() or f"MCP step '{step_id}' failed"
            raise ValueError(error)

        result_payload = McpResult(
            ok=True,
            text=f"{server_name}.{tool_name} completed successfully.",
            data=result,
        )

        raw_next = step.get("next")
        if raw_next is None:
            self.store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                context=context,
            )
            return StepExecutionResult(
                status=StepExecutionStatus.COMPLETED,
                result=result_payload,
            )

        next_step_id = str(raw_next).strip()
        if not next_step_id:
            raise ValueError(f"Step '{step_id}' requires non-empty next")

        self.store.update_run(
            current_step.run_id,
            status=RunStatus.RUNNING,
            current=next_step_id,
            context=context,
        )
        return StepExecutionResult(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
            result=result_payload,
        )
