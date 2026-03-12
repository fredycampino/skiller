from typing import Any

from skiller.application.use_cases.complete_run import CompleteRunUseCase
from skiller.application.use_cases.execute_assign_step import (
    ExecuteAssignStepUseCase,
)
from skiller.application.use_cases.execute_llm_prompt_step import ExecuteLlmPromptStepUseCase
from skiller.application.use_cases.execute_mcp_step import (
    ExecuteMcpStepUseCase,
)
from skiller.application.use_cases.execute_notify_step import (
    ExecuteNotifyStepUseCase,
)
from skiller.application.use_cases.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.execute_wait_webhook_step import ExecuteWaitWebhookStepUseCase
from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.application.use_cases.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.render_current_step import (
    CurrentStepStatus,
    RenderCurrentStepUseCase,
    StepType,
)
from skiller.application.use_cases.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.render_mcp_config import RenderMcpConfigStatus, RenderMcpConfigUseCase
from skiller.application.use_cases.remove_webhook import RemoveWebhookStatus, RemoveWebhookUseCase
from skiller.application.use_cases.resume_run import ResumeRunStatus, ResumeRunUseCase
from skiller.application.use_cases.start_run import StartRunUseCase
from skiller.application.use_cases.step_execution_result import StepExecutionResult, StepExecutionStatus
from skiller.domain.run_model import RunStatus, SkillSource


class RuntimeApplicationService:
    def __init__(
        self,
        start_run_use_case: StartRunUseCase,
        complete_run_use_case: CompleteRunUseCase,
        fail_run_use_case: FailRunUseCase,
        get_start_step_use_case: GetStartStepUseCase,
        render_current_step_use_case: RenderCurrentStepUseCase,
        render_mcp_config_use_case: RenderMcpConfigUseCase,
        execute_assign_step_use_case: ExecuteAssignStepUseCase,
        execute_llm_prompt_step_use_case: ExecuteLlmPromptStepUseCase,
        execute_mcp_step_use_case: ExecuteMcpStepUseCase,
        execute_notify_step_use_case: ExecuteNotifyStepUseCase,
        execute_switch_step_use_case: ExecuteSwitchStepUseCase,
        execute_when_step_use_case: ExecuteWhenStepUseCase,
        execute_wait_webhook_step_use_case: ExecuteWaitWebhookStepUseCase,
        handle_webhook_use_case: HandleWebhookUseCase,
        register_webhook_use_case: RegisterWebhookUseCase,
        remove_webhook_use_case: RemoveWebhookUseCase,
        resume_run_use_case: ResumeRunUseCase,
        get_run_status_use_case: GetRunStatusUseCase,
    ) -> None:
        self.start_run_use_case = start_run_use_case
        self.complete_run_use_case = complete_run_use_case
        self.fail_run_use_case = fail_run_use_case
        self.get_start_step_use_case = get_start_step_use_case
        self.render_current_step_use_case = render_current_step_use_case
        self.render_mcp_config_use_case = render_mcp_config_use_case
        self.execute_assign_step_use_case = execute_assign_step_use_case
        self.execute_llm_prompt_step_use_case = execute_llm_prompt_step_use_case
        self.execute_mcp_step_use_case = execute_mcp_step_use_case
        self.execute_notify_step_use_case = execute_notify_step_use_case
        self.execute_switch_step_use_case = execute_switch_step_use_case
        self.execute_when_step_use_case = execute_when_step_use_case
        self.execute_wait_webhook_step_use_case = execute_wait_webhook_step_use_case
        self.handle_webhook_use_case = handle_webhook_use_case
        self.register_webhook_use_case = register_webhook_use_case
        self.remove_webhook_use_case = remove_webhook_use_case
        self.resume_run_use_case = resume_run_use_case
        self.get_run_status_use_case = get_run_status_use_case

    def start_run(
        self,
        skill_ref: str,
        inputs: dict[str, Any],
        *,
        skill_source: str = SkillSource.INTERNAL.value,
    ) -> dict[str, str]:
        run_id = self.start_run_use_case.execute(skill_ref, inputs, skill_source=skill_source)
        try:
            self.get_start_step_use_case.execute(run_id)
        except Exception as exc:  # noqa: BLE001
            self.fail_run_use_case.execute(run_id, error=str(exc))

        self._run_steps_loop(run_id)
        run = self.get_run_status_use_case.execute(run_id)
        status = str(run.status) if run else RunStatus.FAILED.value
        return {"run_id": run_id, "status": status}

    def handle_webhook(
        self,
        webhook: str,
        key: str,
        payload: dict[str, Any],
        dedup_key: str | None = None,
    ) -> dict[str, Any]:
        final_dedup_key = dedup_key or ""
        result = self.handle_webhook_use_case.execute(webhook, key, payload, dedup_key=final_dedup_key)
        resumed_runs: list[str] = []
        for run_id in result.run_ids:
            resume_result = self.resume_run_use_case.execute(run_id, source="webhook")
            if resume_result.status == ResumeRunStatus.RESUMED:
                self._run_steps_loop(run_id)
                resumed_runs.append(run_id)
        return {
            "accepted": result.accepted,
            "duplicate": result.duplicate,
            "webhook": webhook,
            "key": key,
            "matched_runs": resumed_runs,
        }

    def register_webhook(self, webhook: str) -> dict[str, Any]:
        result = self.register_webhook_use_case.execute(webhook)
        payload = {
            "webhook": result.webhook,
            "status": result.status.value,
        }
        if result.secret is not None:
            payload["secret"] = result.secret
        if result.enabled is not None:
            payload["enabled"] = result.enabled
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def remove_webhook(self, webhook: str) -> dict[str, Any]:
        result = self.remove_webhook_use_case.execute(webhook)
        payload = {
            "webhook": result.webhook,
            "status": result.status.value,
            "removed": result.status == RemoveWebhookStatus.REMOVED,
        }
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def resume_run(self, run_id: str) -> dict[str, Any]:
        result = self.resume_run_use_case.execute(run_id, source="manual")
        if result.status == ResumeRunStatus.RESUMED:
            self._run_steps_loop(run_id)
        run = self.get_run_status_use_case.execute(run_id)
        status = str(run.status) if run else RunStatus.FAILED.value
        return {"run_id": run_id, "resume_status": result.status.value, "status": status}

    def _run_steps_loop(self, run_id: str) -> None:
        try:
            while True:
                result = self.render_current_step_use_case.execute(run_id)
                status = result.status

                if status == CurrentStepStatus.RUN_NOT_FOUND:
                    return

                if status == CurrentStepStatus.DONE:
                    self.complete_run_use_case.execute(run_id)
                    return

                if status in {
                    CurrentStepStatus.CANCELLED,
                    CurrentStepStatus.WAITING,
                    CurrentStepStatus.SUCCEEDED,
                    CurrentStepStatus.FAILED,
                }:
                    return

                if status in {CurrentStepStatus.INVALID_SKILL, CurrentStepStatus.INVALID_STEP}:
                    self.fail_run_use_case.execute(run_id, error=f"Run '{run_id}' is invalid: status={status}")
                    return

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
                            render_result.error or f"Invalid MCP config for step '{current_step.step_id}'"
                        )

                    execution_result = self.execute_mcp_step_use_case.execute(current_step, render_result.mcp_config)

                elif is_ready and current_step.step_type == StepType.WAIT_WEBHOOK:
                    execution_result = self.execute_wait_webhook_step_use_case.execute(current_step)

                elif is_ready and current_step.step_type == StepType.SWITCH:
                    execution_result = self.execute_switch_step_use_case.execute(current_step)

                elif is_ready and current_step.step_type == StepType.WHEN:
                    execution_result = self.execute_when_step_use_case.execute(current_step)

                elif is_ready and current_step:
                    step_type = current_step.step_type.value
                    step_id = current_step.step_id
                    self.fail_run_use_case.execute(
                        run_id,
                        error=(
                            f"Unsupported step type '{step_type}' in step '{step_id}': "
                            "only 'assign', 'llm_prompt', 'mcp', 'notify', 'switch', 'wait_webhook' and 'when' are enabled in run loop"
                        ),
                    )
                    return

                if execution_result is None:
                    raise ValueError(f"Run '{run_id}' reached unexpected loop state")

                if execution_result.status == StepExecutionStatus.NEXT:
                    continue

                if execution_result.status == StepExecutionStatus.COMPLETED:
                    self.complete_run_use_case.execute(run_id)
                    return

                if execution_result.status == StepExecutionStatus.WAITING:
                    return

                raise ValueError(f"Unsupported step execution status '{execution_result.status}'")

        except Exception as exc:  # noqa: BLE001
            self.fail_run_use_case.execute(run_id, error=str(exc))
