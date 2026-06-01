from dataclasses import dataclass
from enum import Enum

from skiller.application.use_cases.execute.execute_agent_step import (
    ExecuteAgentStepUseCase,
)
from skiller.application.use_cases.execute.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute.execute_notify_step import (
    ExecuteNotifyStepUseCase,
)
from skiller.application.use_cases.execute.execute_send_step import ExecuteSendStepUseCase
from skiller.application.use_cases.execute.execute_shell_step import ExecuteShellStepUseCase
from skiller.application.use_cases.execute.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute.execute_wait_channel_step import (
    ExecuteWaitChannelStepUseCase,
)
from skiller.application.use_cases.execute.execute_wait_input_step import (
    ExecuteWaitInputStepUseCase,
)
from skiller.application.use_cases.execute.execute_wait_webhook_step import (
    ExecuteWaitWebhookStepUseCase,
)
from skiller.application.use_cases.execute.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.render.render_current_step import (
    RenderCurrentStepUseCase,
)
from skiller.application.use_cases.render.render_mcp_config import (
    RenderMcpConfigStatus,
    RenderMcpConfigUseCase,
)
from skiller.application.use_cases.run.append_runtime_event import AppendRuntimeEventUseCase
from skiller.application.use_cases.run.complete_run import CompleteRunUseCase
from skiller.application.use_cases.run.fail_run import FailRunUseCase
from skiller.application.use_cases.run.sync_snapshot import SyncSnapshotUseCase
from skiller.domain.event.event_model import (
    RunFinishedPayload,
    RuntimeEventType,
    RunWaitingPayload,
    StepErrorPayload,
    StepStartedPayload,
    StepSuccessPayload,
)
from skiller.domain.step.current_step_model import CurrentStep, CurrentStepStatus
from skiller.domain.step.step_execution_result_model import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.step.step_type import StepType


class RunExecutionStatus(str, Enum):
    RUN_NOT_FOUND = CurrentStepStatus.RUN_NOT_FOUND.value
    WAITING = CurrentStepStatus.WAITING.value
    SUCCEEDED = CurrentStepStatus.SUCCEEDED.value
    FAILED = CurrentStepStatus.FAILED.value
    CANCELLED = CurrentStepStatus.CANCELLED.value


@dataclass(frozen=True)
class RunExecutionResult:
    run_id: str
    status: RunExecutionStatus
    error: str | None = None


class RunExecutor:
    def __init__(
        self,
        complete_run_use_case: CompleteRunUseCase,
        fail_run_use_case: FailRunUseCase,
        append_runtime_event_use_case: AppendRuntimeEventUseCase,
        sync_snapshot_use_case: SyncSnapshotUseCase,
        render_current_step_use_case: RenderCurrentStepUseCase,
        render_mcp_config_use_case: RenderMcpConfigUseCase,
        execute_agent_step_use_case: ExecuteAgentStepUseCase,
        execute_assign_step_use_case: ExecuteAssignStepUseCase,
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
        self.sync_snapshot_use_case = sync_snapshot_use_case
        self.render_current_step_use_case = render_current_step_use_case
        self.render_mcp_config_use_case = render_mcp_config_use_case
        self.execute_agent_step_use_case = execute_agent_step_use_case
        self.execute_assign_step_use_case = execute_assign_step_use_case
        self.execute_mcp_step_use_case = execute_mcp_step_use_case
        self.execute_notify_step_use_case = execute_notify_step_use_case
        self.execute_send_step_use_case = execute_send_step_use_case
        self.execute_shell_step_use_case = execute_shell_step_use_case
        self.execute_switch_step_use_case = execute_switch_step_use_case
        self.execute_when_step_use_case = execute_when_step_use_case
        self.execute_wait_input_step_use_case = execute_wait_input_step_use_case
        self.execute_wait_webhook_step_use_case = execute_wait_webhook_step_use_case
        self.execute_wait_channel_step_use_case = execute_wait_channel_step_use_case

    def run(self, run_id: str) -> RunExecutionResult:
        current_step: CurrentStep | None = None
        try:
            while True:
                self.sync_snapshot_use_case.execute(run_id)
                result = self.render_current_step_use_case.execute(run_id)
                status = result.status

                if status == CurrentStepStatus.RUN_NOT_FOUND:
                    return self.finish(run_id, RunExecutionStatus.RUN_NOT_FOUND)

                if status == CurrentStepStatus.DONE:
                    self.complete_run_use_case.execute(run_id)
                    self._append_run_finished(run_id, status=RunExecutionStatus.SUCCEEDED)
                    return self.finish(run_id, RunExecutionStatus.SUCCEEDED)

                if status == CurrentStepStatus.CANCELLED:
                    return self.finish(run_id, RunExecutionStatus.CANCELLED)

                if status == CurrentStepStatus.WAITING:
                    return self.finish(run_id, RunExecutionStatus.WAITING)

                if status == CurrentStepStatus.SUCCEEDED:
                    return self.finish(run_id, RunExecutionStatus.SUCCEEDED)

                if status == CurrentStepStatus.FAILED:
                    return self.finish(run_id, RunExecutionStatus.FAILED)

                if status in {CurrentStepStatus.INVALID_SKILL, CurrentStepStatus.INVALID_STEP}:
                    error = f"Run '{run_id}' is invalid: status={status}"
                    return self.fail(run_id, step=None, error=error)

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
                    self._append_run_finished(run_id, status=RunExecutionStatus.SUCCEEDED)
                    return self.finish(run_id, RunExecutionStatus.SUCCEEDED)

                if execution_result.status == StepExecutionStatus.WAITING:
                    self._append_run_waiting(run_id, current_step, execution_result)
                    return self.finish(run_id, RunExecutionStatus.WAITING)

                raise ValueError(f"Unsupported step execution status '{execution_result.status}'")

        except Exception as exc:  # noqa: BLE001
            return self.fail(run_id, step=current_step, error=str(exc))

    def finish(
        self,
        run_id: str,
        status: RunExecutionStatus,
    ) -> RunExecutionResult:
        result = RunExecutionResult(run_id=run_id, status=status)
        self.on_finish(result)
        return result

    def fail(
        self,
        run_id: str,
        *,
        step: CurrentStep | None,
        error: str,
    ) -> RunExecutionResult:
        if step is not None:
            self._append_step_error(run_id, step, error)

        self.fail_run_use_case.execute(run_id, error=error)
        self._append_run_finished(run_id, status=RunExecutionStatus.FAILED, error=error)

        result = RunExecutionResult(
            run_id=run_id,
            status=RunExecutionStatus.FAILED,
            error=error,
        )
        self.on_error(result)
        return result

    def on_finish(self, result: RunExecutionResult) -> None:
        pass

    def on_error(self, result: RunExecutionResult) -> None:
        pass

    def _execute_ready_step(self, current_step: CurrentStep) -> StepAdvance:
        if current_step.step_type == StepType.AGENT:
            return self.execute_agent_step_use_case.execute(current_step)

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
            f"'{current_step.step_id}': only 'agent', 'assign', 'mcp', "
            "'notify', 'send', 'shell', "
            "'switch', 'wait_channel', 'wait_input', 'wait_webhook' and 'when' are enabled "
            "in run loop"
        )

    def _append_step_started(self, run_id: str, current_step: CurrentStep) -> None:
        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.STEP_STARTED,
            step_id=current_step.step_id,
            step_type=current_step.step_type.value,
            payload=StepStartedPayload(),
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
            step_type=execution_result.execution.step_type.value,
            payload=StepSuccessPayload(
                output=execution_result.execution.to_public_output_dict(),
                next=execution_result.next_step_id,
            ),
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
            step_type=execution_result.execution.step_type.value,
            payload=RunWaitingPayload(
                output=execution_result.execution.to_public_output_dict(),
            ),
        )

    def _append_step_error(self, run_id: str, current_step: CurrentStep, error: str) -> None:
        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.STEP_ERROR,
            step_id=current_step.step_id,
            step_type=current_step.step_type.value,
            payload=StepErrorPayload(
                error=error,
            ),
        )

    def _append_run_finished(
        self,
        run_id: str,
        *,
        status: RunExecutionStatus,
        error: str | None = None,
    ) -> None:
        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.RUN_FINISHED,
            payload=RunFinishedPayload(status=status.value, error=error),
        )
