from skiller.application.tools.shell import ShellProcessTool
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.application.use_cases.shared.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.run.steering_model import SteeringStepInterrupt
from skiller.domain.shared.large_result_truncator import LargeResultTruncator
from skiller.domain.shared.steering_port import SteeringPort
from skiller.domain.step.execution_output_store_port import (
    ExecutionOutputStorePort,
)
from skiller.domain.step.step_execution_model import ShellOutput, StepExecution
from skiller.domain.tool.tool_contract import ToolInput, ToolResult
from skiller.domain.tool.tool_process_model import (
    ToolProcessInterrupt,
    ToolProcessInterruptSignal,
    ToolProcessRequest,
    ToolProcessWait,
    ToolProcessWaitStatus,
)
from skiller.domain.tool.tool_process_port import ToolProcessPort


class ExecuteShellStepUseCase(ToolProcessInterruptSignal):
    def __init__(
        self,
        store: RunStorePort,
        execution_output_store: ExecutionOutputStorePort,
        shell_tool: ShellProcessTool,
        process_runner: ToolProcessPort,
        agent_steering_store: SteeringPort,
        large_result_truncator: LargeResultTruncator,
    ) -> None:
        self.store = store
        self.execution_output_store = execution_output_store
        self.shell_tool = shell_tool
        self.process_runner = process_runner
        self.agent_steering_store = agent_steering_store
        self.large_result_truncator = large_result_truncator

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step_id = current_step.step_id
        step = current_step.step

        check = self._parse_check(step_id=step_id, value=step.get("check"))
        large_result = self._parse_large_result(step_id=step_id, value=step.get("large_result"))
        shell_request_result = self.shell_tool.request(
            ToolInput(
                run_id=current_step.run_id,
                step_id=step_id,
                tool_call_id=step_id,
                args={
                    "command": step.get("command"),
                    "cwd": step.get("cwd"),
                    "env": step.get("env"),
                    "timeout": step.get("timeout"),
                },
            )
        )
        if not shell_request_result.ok:
            raise ValueError(shell_request_result.error or f"Shell step '{step_id}' request failed")
        if shell_request_result.request is None:
            raise ValueError(f"Shell step '{step_id}' request returned no request")
        shell_request = shell_request_result.request
        policy_result = self.shell_tool.policy(shell_request)
        if not policy_result.ok:
            raise ValueError(policy_result.error or f"Shell step '{step_id}' was blocked")
        if policy_result.request is None:
            raise ValueError(f"Shell step '{step_id}' policy returned no request")
        shell_request = policy_result.request

        process_request = self.shell_tool.call(shell_request)
        result = self._execute_shell_process(
            run_id=current_step.run_id,
            step_id=step_id,
            request=process_request,
        )

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

    def _execute_shell_process(
        self,
        *,
        run_id: str,
        step_id: str,
        request: ToolProcessRequest,
    ) -> ToolResult:
        handle = self.process_runner.popen(request)
        wait_result = self.process_runner.wait(
            ToolProcessWait(
                handle=handle,
                timeout=request.timeout,
                interrupt=ToolProcessInterrupt(
                    run_id=run_id,
                    signal=self,
                ),
            )
        )
        if wait_result.status == ToolProcessWaitStatus.TIMEOUT:
            raise ValueError(
                f"Shell step '{step_id}' timed out after "
                f"{self.shell_tool.format_timeout(request.timeout)}"
            )
        if wait_result.status == ToolProcessWaitStatus.INTERRUPTED:
            raise ValueError(f"Shell step '{step_id}' was interrupted")
        if wait_result.output is None:
            raise ValueError(f"Shell step '{step_id}' did not return process output")
        return self.shell_tool.result(wait_result.output)

    def is_interrupted(self, run_id: str) -> bool:
        return bool(self.agent_steering_store.pop(run_id, SteeringStepInterrupt))

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
