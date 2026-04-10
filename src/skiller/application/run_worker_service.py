from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.application.use_cases.append_runtime_event import (
    AppendRuntimeEventUseCase,
    RuntimeEventType,
)
from skiller.application.use_cases.complete_run import CompleteRunUseCase
from skiller.application.use_cases.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute_llm_prompt_step import ExecuteLlmPromptStepUseCase
from skiller.application.use_cases.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.execute_send_step import ExecuteSendStepUseCase
from skiller.application.use_cases.execute_shell_step import ExecuteShellStepUseCase
from skiller.application.use_cases.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute_wait_channel_step import ExecuteWaitChannelStepUseCase
from skiller.application.use_cases.execute_wait_input_step import ExecuteWaitInputStepUseCase
from skiller.application.use_cases.execute_wait_webhook_step import ExecuteWaitWebhookStepUseCase
from skiller.application.use_cases.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.application.use_cases.render_current_step import (
    CurrentStep,
    CurrentStepStatus,
    RenderCurrentStepUseCase,
    StepType,
)
from skiller.application.use_cases.render_mcp_config import (
    RenderMcpConfigStatus,
    RenderMcpConfigUseCase,
)
from skiller.application.use_cases.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)


class RunWorkerStatus(str, Enum):
    RUN_NOT_FOUND = CurrentStepStatus.RUN_NOT_FOUND.value
    WAITING = CurrentStepStatus.WAITING.value
    SUCCEEDED = CurrentStepStatus.SUCCEEDED.value
    FAILED = CurrentStepStatus.FAILED.value
    CANCELLED = CurrentStepStatus.CANCELLED.value


@dataclass(frozen=True)
class RunWorkerResult:
    run_id: str
    status: RunWorkerStatus
    error: str | None = None


class RunWorkerService:
    def __init__(
        self,
        complete_run_use_case: CompleteRunUseCase,
        fail_run_use_case: FailRunUseCase,
        append_runtime_event_use_case: AppendRuntimeEventUseCase,
        render_current_step_use_case: RenderCurrentStepUseCase,
        render_mcp_config_use_case: RenderMcpConfigUseCase,
        execute_assign_step_use_case: ExecuteAssignStepUseCase,
        execute_llm_prompt_step_use_case: ExecuteLlmPromptStepUseCase,
        execute_mcp_step_use_case: ExecuteMcpStepUseCase,
        execute_notify_step_use_case: ExecuteNotifyStepUseCase,
        execute_switch_step_use_case: ExecuteSwitchStepUseCase,
        execute_when_step_use_case: ExecuteWhenStepUseCase,
        execute_wait_webhook_step_use_case: ExecuteWaitWebhookStepUseCase,
        execute_send_step_use_case: ExecuteSendStepUseCase | None = None,
        execute_wait_channel_step_use_case: ExecuteWaitChannelStepUseCase | None = None,
        execute_wait_input_step_use_case: ExecuteWaitInputStepUseCase | None = None,
        execute_shell_step_use_case: ExecuteShellStepUseCase | None = None,
    ) -> None:
        self.complete_run_use_case = complete_run_use_case
        self.fail_run_use_case = fail_run_use_case
        self.append_runtime_event_use_case = append_runtime_event_use_case
        self.render_current_step_use_case = render_current_step_use_case
        self.render_mcp_config_use_case = render_mcp_config_use_case
        self.execute_assign_step_use_case = execute_assign_step_use_case
        self.execute_llm_prompt_step_use_case = execute_llm_prompt_step_use_case
        self.execute_mcp_step_use_case = execute_mcp_step_use_case
        self.execute_notify_step_use_case = execute_notify_step_use_case
        self.execute_send_step_use_case = execute_send_step_use_case
        self.execute_shell_step_use_case = execute_shell_step_use_case
        self.execute_switch_step_use_case = execute_switch_step_use_case
        self.execute_when_step_use_case = execute_when_step_use_case
        self.execute_wait_input_step_use_case = execute_wait_input_step_use_case
        self.execute_wait_webhook_step_use_case = execute_wait_webhook_step_use_case
        self.execute_wait_channel_step_use_case = execute_wait_channel_step_use_case

    def run(self, run_id: str) -> RunWorkerResult:
        current_step: CurrentStep | None = None
        try:
            while True:
                result = self.render_current_step_use_case.execute(run_id)
                status = result.status

                if status == CurrentStepStatus.RUN_NOT_FOUND:
                    return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.RUN_NOT_FOUND)

                if status == CurrentStepStatus.DONE:
                    self.complete_run_use_case.execute(run_id)
                    self._append_run_finished(run_id, status=RunWorkerStatus.SUCCEEDED)
                    return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.SUCCEEDED)

                if status == CurrentStepStatus.CANCELLED:
                    return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.CANCELLED)

                if status == CurrentStepStatus.WAITING:
                    return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.WAITING)

                if status == CurrentStepStatus.SUCCEEDED:
                    return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.SUCCEEDED)

                if status == CurrentStepStatus.FAILED:
                    return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.FAILED)

                if status in {CurrentStepStatus.INVALID_SKILL, CurrentStepStatus.INVALID_STEP}:
                    error = f"Run '{run_id}' is invalid: status={status}"
                    self.fail_run_use_case.execute(run_id, error=error)
                    self._append_run_finished(run_id, status=RunWorkerStatus.FAILED, error=error)
                    return RunWorkerResult(
                        run_id=run_id, status=RunWorkerStatus.FAILED, error=error
                    )

                current_step = result.current_step
                is_ready = status == CurrentStepStatus.READY and current_step
                execution_result: StepAdvance | None = None

                if is_ready and current_step:
                    self._append_step_started(run_id, current_step)
                    execution_result = self._execute_ready_step(current_step)

                if execution_result is None:
                    raise ValueError(f"Run '{run_id}' reached unexpected loop state")

                if execution_result.status == StepExecutionStatus.NEXT:
                    self._append_step_success(run_id, current_step, execution_result)
                    continue

                if execution_result.status == StepExecutionStatus.COMPLETED:
                    self._append_step_success(run_id, current_step, execution_result)
                    self.complete_run_use_case.execute(run_id)
                    self._append_run_finished(run_id, status=RunWorkerStatus.SUCCEEDED)
                    return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.SUCCEEDED)

                if execution_result.status == StepExecutionStatus.WAITING:
                    self._append_run_waiting(run_id, current_step, execution_result)
                    return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.WAITING)

                raise ValueError(f"Unsupported step execution status '{execution_result.status}'")

        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            if current_step is not None:
                self._append_step_error(run_id, current_step, error)
            self.fail_run_use_case.execute(run_id, error=error)
            self._append_run_finished(run_id, status=RunWorkerStatus.FAILED, error=error)
            return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.FAILED, error=error)

    def _execute_ready_step(self, current_step: CurrentStep) -> StepAdvance:
        if current_step.step_type == StepType.NOTIFY:
            return self.execute_notify_step_use_case.execute(current_step)

        if current_step.step_type == StepType.SEND:
            if self.execute_send_step_use_case is None:
                raise ValueError("send step executor is not configured")
            return self.execute_send_step_use_case.execute(current_step)

        if current_step.step_type == StepType.ASSIGN:
            return self.execute_assign_step_use_case.execute(current_step)

        if current_step.step_type == StepType.SHELL:
            if self.execute_shell_step_use_case is None:
                raise ValueError("shell step executor is not configured")
            return self.execute_shell_step_use_case.execute(current_step)

        if current_step.step_type == StepType.LLM_PROMPT:
            return self.execute_llm_prompt_step_use_case.execute(current_step)

        if current_step.step_type == StepType.MCP:
            render_result = self.render_mcp_config_use_case.execute(current_step)
            if render_result.status != RenderMcpConfigStatus.RENDERED:
                raise ValueError(
                    render_result.error or f"Invalid MCP config for step '{current_step.step_id}'"
                )

            return self.execute_mcp_step_use_case.execute(current_step, render_result.mcp_config)

        if current_step.step_type == StepType.WAIT_INPUT:
            if self.execute_wait_input_step_use_case is None:
                raise ValueError("wait_input step executor is not configured")
            return self.execute_wait_input_step_use_case.execute(current_step)

        if current_step.step_type == StepType.WAIT_WEBHOOK:
            return self.execute_wait_webhook_step_use_case.execute(current_step)

        if current_step.step_type == StepType.WAIT_CHANNEL:
            if self.execute_wait_channel_step_use_case is None:
                raise ValueError("wait_channel step executor is not configured")
            return self.execute_wait_channel_step_use_case.execute(current_step)

        if current_step.step_type == StepType.SWITCH:
            return self.execute_switch_step_use_case.execute(current_step)

        if current_step.step_type == StepType.WHEN:
            return self.execute_when_step_use_case.execute(current_step)

        raise ValueError(
            f"Unsupported step type '{current_step.step_type.value}' in step "
            f"'{current_step.step_id}': only 'assign', 'llm_prompt', 'mcp', "
            "'notify', 'send', 'shell', "
            "'switch', 'wait_channel', 'wait_input', 'wait_webhook' and 'when' are enabled "
            "in run loop"
        )

    def _append_step_started(self, run_id: str, current_step: CurrentStep) -> None:
        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.STEP_STARTED,
            step_id=current_step.step_id,
            step_type=current_step.step_type,
        )

    def _append_step_success(
        self,
        run_id: str,
        current_step: CurrentStep,
        execution_result: StepAdvance,
    ) -> None:
        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.STEP_SUCCESS,
            step_id=current_step.step_id,
            execution=execution_result.execution,
            next_step_id=execution_result.next_step_id,
        )

    def _append_run_waiting(
        self,
        run_id: str,
        current_step: CurrentStep,
        execution_result: StepAdvance,
    ) -> None:
        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.RUN_WAITING,
            step_id=current_step.step_id,
            execution=execution_result.execution,
        )

    def _append_step_error(self, run_id: str, current_step: CurrentStep, error: str) -> None:
        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.STEP_ERROR,
            step_id=current_step.step_id,
            step_type=current_step.step_type,
            error=error,
        )

    def _append_run_finished(
        self,
        run_id: str,
        *,
        status: RunWorkerStatus,
        error: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {"status": status.value}
        if error is not None:
            payload["error"] = error
        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.RUN_FINISHED,
            payload=payload,
        )
