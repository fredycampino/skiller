from typing import Any

from skiller.application.runs.models import (
    ResumeRunApplicationResult,
    RunRequest,
    RunResult,
    WorkerStartResult,
)
from skiller.application.use_cases.run.delete_run import (
    DeleteRunResult,
    DeleteRunStatus,
)
from skiller.application.use_cases.run.mark_notify_action_done import (
    MarkNotifyActionDoneInput,
    MarkNotifyActionDoneResult,
    MarkNotifyActionDoneStatus,
)
from skiller.domain.flow.flow_reference import FlowReference


class RunServiceMapper:
    def to_create_input(
        self,
        flow_reference: str,
        inputs: dict[str, Any],
    ) -> RunRequest:
        sanitized_reference = flow_reference.strip()
        if not sanitized_reference:
            raise ValueError("flow reference is required")
        return RunRequest(
            reference=FlowReference(sanitized_reference),
            inputs=inputs,
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
        action_uid: str,
    ) -> MarkNotifyActionDoneInput:
        normalized_run_id = run_id.strip()
        normalized_action_uid = action_uid.strip()
        if not normalized_run_id:
            raise ValueError("run_id is required")
        if not normalized_action_uid:
            raise ValueError("action_uid is required")
        return MarkNotifyActionDoneInput(
            run_id=normalized_run_id,
            action_uid=normalized_action_uid,
        )

    def to_action_done_dict(
        self,
        result: MarkNotifyActionDoneResult,
    ) -> dict[str, Any]:
        payload = {
            "run_id": result.run_id,
            "action_uid": result.action_uid,
            "status": result.status.value,
            "done": result.status == MarkNotifyActionDoneStatus.DONE,
            "changed": result.changed,
        }
        if result.step_id is not None:
            payload["step_id"] = result.step_id
        if result.error is not None:
            payload["error"] = result.error
        return payload
