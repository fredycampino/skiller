from skiller.application.ports.execution_output_store_port import ExecutionOutputStorePort
from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.ports.shell_port import ShellPort
from skiller.application.tools.shell import ShellTool, ShellToolAdapter
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.application.use_cases.shared.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.run.run_model import RunStatus
from skiller.domain.shared.large_result_truncator import LargeResultTruncator
from skiller.domain.step.step_execution_model import ShellOutput, StepExecution
from skiller.domain.tool.tool_contract import ToolResult


class ExecuteShellStepUseCase:
    def __init__(
        self,
        store: RunStorePort,
        execution_output_store: ExecutionOutputStorePort,
        shell: ShellPort,
        large_result_truncator: LargeResultTruncator,
    ) -> None:
        self.store = store
        self.execution_output_store = execution_output_store
        self.shell_tool_adapter = ShellToolAdapter()
        self.shell_tool = ShellTool(shell)
        self.large_result_truncator = large_result_truncator

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step_id = current_step.step_id
        step = current_step.step

        check = self._parse_check(step_id=step_id, value=step.get("check"))
        large_result = self._parse_large_result(step_id=step_id, value=step.get("large_result"))
        shell_request = self.shell_tool_adapter.build_request(
            step_id=step_id,
            value={
                "command": step.get("command"),
                "cwd": step.get("cwd"),
                "env": step.get("env"),
                "timeout": step.get("timeout"),
            },
        )

        try:
            result = self.shell_tool.execute(shell_request)
        except TimeoutError as exc:
            raise ValueError(
                f"Shell step '{step_id}' timed out after "
                f"{self.shell_tool_adapter.format_timeout(shell_request.timeout)}"
            ) from exc

        result_data = result.data
        if check and bool(result_data.get("ok")) is False:
            exit_code = int(result_data.get("exit_code", 0))
            raise ValueError(f"Shell step '{step_id}' failed with exit code {exit_code}")

        output_payload, body_ref = self._build_output_payload(
            run_id=current_step.run_id,
            step_id=step_id,
            result=result,
            large_result=large_result,
        )
        execution = StepExecution(
            step_type=current_step.step_type,
            input={
                "command": shell_request.command,
                "cwd": shell_request.cwd,
                "env": shell_request.env,
                "timeout": shell_request.timeout,
                "check": check,
                "large_result": large_result,
            },
            evaluation={},
            output=ShellOutput(
                text=(
                    self._build_output_text(output_payload)
                    if large_result
                    else (result.text or self._build_output_text(output_payload))
                ),
                ok=bool(output_payload.get("ok")),
                exit_code=int(output_payload.get("exit_code", 0)),
                stdout=str(output_payload.get("stdout", "")),
                stderr=str(output_payload.get("stderr", "")),
                body_ref=body_ref,
            ),
        )
        current_step.context.step_executions[step_id] = execution
        return self._advance(current_step=current_step, execution=execution)

    def _parse_check(self, *, step_id: str, value: object) -> bool:
        if value is None:
            return True
        if isinstance(value, bool):
            return value
        raise ValueError(f"Step '{step_id}' requires boolean check")

    def _parse_large_result(self, *, step_id: str, value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        raise ValueError(f"Step '{step_id}' requires boolean large_result")

    def _build_output_payload(
        self,
        *,
        run_id: str,
        step_id: str,
        result: ToolResult,
        large_result: bool,
    ) -> tuple[dict[str, object], str | None]:
        output_payload = {
            "ok": bool(result.data.get("ok")),
            "exit_code": int(result.data.get("exit_code", 0)),
            "stdout": str(result.data.get("stdout", "")),
            "stderr": str(result.data.get("stderr", "")),
        }
        if not large_result:
            return output_payload, None

        body_ref = self.execution_output_store.store_execution_output(
            run_id=run_id,
            step_id=step_id,
            output_body={"value": output_payload},
        )
        truncated = self.large_result_truncator.truncate(output_payload)
        return {
            "ok": bool(truncated.get("ok")),
            "exit_code": int(truncated.get("exit_code", 0)),
            "stdout": str(truncated.get("stdout", "")),
            "stderr": str(truncated.get("stderr", "")),
        }, body_ref

    def _build_output_text(self, value: dict[str, object]) -> str:
        ok = bool(value.get("ok"))
        exit_code = int(value.get("exit_code", 0))
        stdout = str(value.get("stdout", "")).strip()
        stderr = str(value.get("stderr", "")).strip()

        if stdout:
            first_line = stdout.splitlines()[0].strip()
            if first_line:
                return first_line

        if ok:
            return "Command completed successfully."

        if stderr:
            first_line = stderr.splitlines()[0].strip()
            if first_line:
                return first_line

        return f"Command failed with exit code {exit_code}."

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
