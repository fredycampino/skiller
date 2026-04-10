from typing import Any

from skiller.application.ports.execution_output_store_port import ExecutionOutputStorePort
from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.ports.shell_port import ShellPort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.large_result_truncator import LargeResultTruncator
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import ShellOutput, StepExecution


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
        self.shell = shell
        self.large_result_truncator = large_result_truncator

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step_id = current_step.step_id
        step = current_step.step

        command = self._parse_command(step_id=step_id, step=step)
        cwd = self._parse_cwd(step_id=step_id, value=step.get("cwd"))
        env = self._parse_env(step_id=step_id, value=step.get("env"))
        timeout = self._parse_timeout(step_id=step_id, value=step.get("timeout"))
        check = self._parse_check(step_id=step_id, value=step.get("check"))
        large_result = self._parse_large_result(step_id=step_id, value=step.get("large_result"))

        try:
            result = self.shell.run(
                command=command,
                cwd=cwd,
                env=env,
                timeout=timeout,
            )
        except TimeoutError as exc:
            raise ValueError(
                f"Shell step '{step_id}' timed out after {self._format_timeout(timeout)}"
            ) from exc

        if check and result["ok"] is False:
            exit_code = int(result.get("exit_code", 1))
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
                "command": command,
                "cwd": cwd,
                "env": env,
                "timeout": timeout,
                "check": check,
                "large_result": large_result,
            },
            evaluation={},
            output=ShellOutput(
                text=self._build_output_text(output_payload),
                ok=bool(output_payload.get("ok")),
                exit_code=int(output_payload.get("exit_code", 0)),
                stdout=str(output_payload.get("stdout", "")),
                stderr=str(output_payload.get("stderr", "")),
                body_ref=body_ref,
            ),
        )
        current_step.context.step_executions[step_id] = execution
        return self._advance(current_step=current_step, execution=execution)

    def _parse_command(self, *, step_id: str, step: dict[str, Any]) -> str:
        command = str(step.get("command", ""))
        if not command.strip():
            raise ValueError(f"Step '{step_id}' requires command")
        return command

    def _parse_cwd(self, *, step_id: str, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"Step '{step_id}' requires string cwd")
        cwd = value.strip()
        return cwd or None

    def _parse_env(self, *, step_id: str, value: object) -> dict[str, str] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError(f"Step '{step_id}' env must be an object")

        env: dict[str, str] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"Step '{step_id}' env requires non-empty string keys")
            env[key] = str(item)
        return env

    def _parse_timeout(self, *, step_id: str, value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Step '{step_id}' requires integer timeout")
        if value <= 0:
            raise ValueError(f"Step '{step_id}' requires positive timeout")
        return value

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
        result: dict[str, object],
        large_result: bool,
    ) -> tuple[dict[str, object], str | None]:
        output_payload = self._clone(result)
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

    def _format_timeout(self, timeout: int | None) -> str:
        if isinstance(timeout, int):
            return f"{timeout}s"
        return "unknown timeout"

    def _clone(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._clone(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._clone(item) for item in value]
        return value
