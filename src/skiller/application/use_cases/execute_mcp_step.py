from typing import Any

from skiller.application.ports.execution_output_store_port import ExecutionOutputStorePort
from skiller.application.ports.mcp_port import MCPPort
from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.large_result_truncator import LargeResultTruncator
from skiller.domain.mcp_config_model import RenderedMcpConfig
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import McpOutput, StepExecution


class ExecuteMcpStepUseCase:
    def __init__(
        self,
        store: RunStorePort,
        execution_output_store: ExecutionOutputStorePort,
        mcp: MCPPort,
        large_result_truncator: LargeResultTruncator,
    ) -> None:
        self.store = store
        self.execution_output_store = execution_output_store
        self.mcp = mcp
        self.large_result_truncator = large_result_truncator

    def execute(
        self, current_step: CurrentStep, mcp_config: RenderedMcpConfig
    ) -> StepAdvance:
        step_id = current_step.step_id
        step = current_step.step

        server_name = self._parse_server_name(step_id=step_id, step=step)
        tool_name = self._parse_tool_name(step_id=step_id, step=step)
        args = self._parse_args(step_id=step_id, step=step)
        large_result = self._parse_large_result(step_id=step_id, value=step.get("large_result"))

        result = self.mcp.call_tool(server_name, tool_name, args, config=mcp_config)
        self._raise_if_failed(step_id=step_id, result=result)

        output_data, body_ref = self._build_output_payload(
            run_id=current_step.run_id,
            step_id=step_id,
            result=result,
            large_result=large_result,
        )
        execution = StepExecution(
            step_type=current_step.step_type,
            input={
                "server": server_name,
                "tool": tool_name,
                "args": args,
                "large_result": large_result,
            },
            evaluation={"ok": True},
            output=McpOutput(
                text=f"{server_name}.{tool_name} completed successfully.",
                data=output_data,
                body_ref=body_ref,
            ),
        )
        current_step.context.step_executions[step_id] = execution
        return self._advance(current_step=current_step, execution=execution)

    def _parse_server_name(self, *, step_id: str, step: dict[str, Any]) -> str:
        server_name = str(step.get("server", "")).strip()
        if not server_name:
            raise ValueError(f"Step '{step_id}' requires mcp server name in field 'server'")
        return server_name

    def _parse_tool_name(self, *, step_id: str, step: dict[str, Any]) -> str:
        tool_name = str(step.get("tool", "")).strip()
        if not tool_name:
            raise ValueError(f"Step '{step_id}' requires tool name in field 'tool'")
        if tool_name.startswith("mcp."):
            raise ValueError(
                f"Step '{step_id}' invalid tool '{tool_name}'. "
                "For type 'mcp', use plain tool name without "
                "'mcp.<server>.' prefix."
            )
        return tool_name

    def _parse_args(self, *, step_id: str, step: dict[str, Any]) -> dict[str, Any]:
        args = step.get("args", {})
        if not isinstance(args, dict):
            raise ValueError(f"Step '{step_id}' args must be an object")
        return args

    def _parse_large_result(self, *, step_id: str, value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        raise ValueError(f"Step '{step_id}' requires boolean large_result")

    def _raise_if_failed(self, *, step_id: str, result: dict[str, Any]) -> None:
        if result.get("ok") is False:
            error = str(result.get("error", "")).strip() or f"MCP step '{step_id}' failed"
            raise ValueError(error)

    def _build_output_payload(
        self,
        *,
        run_id: str,
        step_id: str,
        result: dict[str, Any],
        large_result: bool,
    ) -> tuple[dict[str, Any], str | None]:
        output_data = self._clone(result)
        if not large_result:
            return output_data, None

        body_ref = self.execution_output_store.store_execution_output(
            run_id=run_id,
            step_id=step_id,
            output_body=output_data,
        )
        return self.large_result_truncator.truncate(result), body_ref

    def _advance(self, *, current_step: CurrentStep, execution: StepExecution) -> StepAdvance:
        step_id = current_step.step_id
        raw_next = current_step.step.get("next")

        if raw_next is None:
            self.store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                context=current_step.context,
            )
            return StepAdvance(
                status=StepExecutionStatus.COMPLETED,
                execution=execution,
            )

        next_step_id = str(raw_next).strip()
        if not next_step_id:
            raise ValueError(f"Step '{step_id}' requires non-empty next")

        self.store.update_run(
            current_step.run_id,
            status=RunStatus.RUNNING,
            current=next_step_id,
            context=current_step.context,
        )
        return StepAdvance(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
            execution=execution,
        )

    def _clone(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._clone(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._clone(item) for item in value]
        return value
