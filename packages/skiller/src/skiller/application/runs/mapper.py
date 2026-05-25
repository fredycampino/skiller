from typing import Any

from skiller.application.runs.models import (
    ResumeRunApplicationResult,
    RunResult,
    WorkerStartResult,
)
from skiller.application.use_cases.run.create_run import CreateRunInput
from skiller.application.use_cases.run.delete_run import (
    DeleteRunResult,
    DeleteRunStatus,
)
from skiller.application.use_cases.run.mark_notify_action_done import (
    MarkNotifyActionDoneInput,
    MarkNotifyActionDoneResult,
    MarkNotifyActionDoneStatus,
)
from skiller.domain.run.run_model import SkillSource


class RunServiceMapper:
    def to_create_input(
        self,
        skill_ref: str,
        inputs: dict[str, Any],
        *,
        skill_source: str,
    ) -> CreateRunInput:
        sanitized_ref = skill_ref.strip()
        parsed_source = self._parse_skill_source(skill_source)
        return CreateRunInput(
            skill_ref=sanitized_ref,
            inputs=inputs,
            skill_source=parsed_source.value,
        )

    def to_run_dict(self, result: RunResult) -> dict[str, str]:
        return {
            "run_id": result.run_id,
            "status": result.status.value,
        }

    def to_worker_start_dict(self, result: WorkerStartResult) -> dict[str, str]:
        return {
            "run_id": result.run_id,
            "start_status": result.start_status.value,
            "status": result.status.value,
        }

    def to_delete_dict(self, result: DeleteRunResult) -> dict[str, Any]:
        payload = {
            "run_id": result.run_id,
            "status": result.status.value,
            "deleted": result.status == DeleteRunStatus.DELETED,
        }
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def to_resume_dict(self, result: ResumeRunApplicationResult) -> dict[str, Any]:
        return {
            "run_id": result.run_id,
            "resume_status": result.resume_status.value,
            "status": result.status.value,
        }

    def to_action_done_input(
        self,
        run_id: str,
        step_id: str,
    ) -> MarkNotifyActionDoneInput:
        normalized_run_id = run_id.strip()
        normalized_step_id = step_id.strip()
        if not normalized_run_id:
            raise ValueError("run_id is required")
        if not normalized_step_id:
            raise ValueError("step_id is required")
        return MarkNotifyActionDoneInput(
            run_id=normalized_run_id,
            step_id=normalized_step_id,
        )

    def to_action_done_dict(
        self,
        result: MarkNotifyActionDoneResult,
    ) -> dict[str, Any]:
        payload = {
            "run_id": result.run_id,
            "step_id": result.step_id,
            "status": result.status.value,
            "done": result.status == MarkNotifyActionDoneStatus.DONE,
            "changed": result.changed,
        }
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def _parse_skill_source(self, skill_source: str) -> SkillSource:
        try:
            return SkillSource(skill_source.strip())
        except ValueError as exc:
            raise ValueError("skill_source is invalid") from exc
