from dataclasses import dataclass
from enum import Enum

from skiller.application.use_cases.complete_run import CompleteRunUseCase
from skiller.application.use_cases.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute_llm_prompt_step import ExecuteLlmPromptStepUseCase
from skiller.application.use_cases.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute_wait_webhook_step import ExecuteWaitWebhookStepUseCase
from skiller.application.use_cases.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.application.use_cases.render_current_step import (
    CurrentStepStatus,
    RenderCurrentStepUseCase,
    StepType,
)
from skiller.application.use_cases.render_mcp_config import (
    RenderMcpConfigStatus,
    RenderMcpConfigUseCase,
)
from skiller.application.use_cases.step_execution_result import (
    StepExecutionResult,
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
        render_current_step_use_case: RenderCurrentStepUseCase,
        render_mcp_config_use_case: RenderMcpConfigUseCase,
        execute_assign_step_use_case: ExecuteAssignStepUseCase,
        execute_llm_prompt_step_use_case: ExecuteLlmPromptStepUseCase,
        execute_mcp_step_use_case: ExecuteMcpStepUseCase,
        execute_notify_step_use_case: ExecuteNotifyStepUseCase,
        execute_switch_step_use_case: ExecuteSwitchStepUseCase,
        execute_when_step_use_case: ExecuteWhenStepUseCase,
        execute_wait_webhook_step_use_case: ExecuteWaitWebhookStepUseCase,
    ) -> None:
        self.complete_run_use_case = complete_run_use_case
        self.fail_run_use_case = fail_run_use_case
        self.render_current_step_use_case = render_current_step_use_case
        self.render_mcp_config_use_case = render_mcp_config_use_case
        self.execute_assign_step_use_case = execute_assign_step_use_case
        self.execute_llm_prompt_step_use_case = execute_llm_prompt_step_use_case
        self.execute_mcp_step_use_case = execute_mcp_step_use_case
        self.execute_notify_step_use_case = execute_notify_step_use_case
        self.execute_switch_step_use_case = execute_switch_step_use_case
        self.execute_when_step_use_case = execute_when_step_use_case
        self.execute_wait_webhook_step_use_case = execute_wait_webhook_step_use_case

    def run(self, run_id: str) -> RunWorkerResult:
        try:
            while True:
                result = self.render_current_step_use_case.execute(run_id)
                status = result.status

                if status == CurrentStepStatus.RUN_NOT_FOUND:
                    return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.RUN_NOT_FOUND)

                if status == CurrentStepStatus.DONE:
                    self.complete_run_use_case.execute(run_id)
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
                    return RunWorkerResult(
                        run_id=run_id, status=RunWorkerStatus.FAILED, error=error
                    )

                current_step = result.current_step
                is_ready = status == CurrentStepStatus.READY and current_step
                execution_result: StepExecutionResult | None = None

                if is_ready and current_step.step_type == StepType.NOTIFY:
                    execution_result = self.execute_notify_step_use_case.execute(current_step)

                elif is_ready and current_step.step_type == StepType.ASSIGN:
                    execution_result = self.execute_assign_step_use_case.execute(current_step)

                elif is_ready and current_step.step_type == StepType.LLM_PROMPT:
                    execution_result = self.execute_llm_prompt_step_use_case.execute(current_step)

                elif is_ready and current_step.step_type == StepType.MCP:
                    render_result = self.render_mcp_config_use_case.execute(current_step)
                    if render_result.status != RenderMcpConfigStatus.RENDERED:
                        raise ValueError(
                            render_result.error
                            or f"Invalid MCP config for step '{current_step.step_id}'"
                        )

                    execution_result = self.execute_mcp_step_use_case.execute(
                        current_step, render_result.mcp_config
                    )

                elif is_ready and current_step.step_type == StepType.WAIT_WEBHOOK:
                    execution_result = self.execute_wait_webhook_step_use_case.execute(current_step)

                elif is_ready and current_step.step_type == StepType.SWITCH:
                    execution_result = self.execute_switch_step_use_case.execute(current_step)

                elif is_ready and current_step.step_type == StepType.WHEN:
                    execution_result = self.execute_when_step_use_case.execute(current_step)

                elif is_ready and current_step:
                    step_type = current_step.step_type.value
                    step_id = current_step.step_id
                    error = (
                        f"Unsupported step type '{step_type}' in step '{step_id}': "
                        "only 'assign', 'llm_prompt', 'mcp', 'notify', 'switch', "
                        "'wait_webhook' and 'when' are enabled in run loop"
                    )
                    self.fail_run_use_case.execute(run_id, error=error)
                    return RunWorkerResult(
                        run_id=run_id, status=RunWorkerStatus.FAILED, error=error
                    )

                if execution_result is None:
                    raise ValueError(f"Run '{run_id}' reached unexpected loop state")

                if execution_result.status == StepExecutionStatus.NEXT:
                    continue

                if execution_result.status == StepExecutionStatus.COMPLETED:
                    self.complete_run_use_case.execute(run_id)
                    return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.SUCCEEDED)

                if execution_result.status == StepExecutionStatus.WAITING:
                    return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.WAITING)

                raise ValueError(f"Unsupported step execution status '{execution_result.status}'")

        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            self.fail_run_use_case.execute(run_id, error=error)
            return RunWorkerResult(run_id=run_id, status=RunWorkerStatus.FAILED, error=error)
