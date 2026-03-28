from typing import Any

from skiller.application.run_worker_service import RunWorkerService
from skiller.application.use_cases.append_runtime_event import (
    AppendRuntimeEventUseCase,
    RuntimeEventType,
)
from skiller.application.use_cases.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.create_run import CreateRunUseCase
from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.application.use_cases.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.handle_input import HandleInputUseCase
from skiller.application.use_cases.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.list_webhooks import ListWebhooksUseCase
from skiller.application.use_cases.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.remove_webhook import RemoveWebhookStatus, RemoveWebhookUseCase
from skiller.application.use_cases.resume_run import ResumeRunStatus, ResumeRunUseCase
from skiller.domain.run_model import RunStatus, SkillSource


class RuntimeApplicationService:
    def __init__(
        self,
        bootstrap_runtime_use_case: BootstrapRuntimeUseCase,
        append_runtime_event_use_case: AppendRuntimeEventUseCase,
        create_run_use_case: CreateRunUseCase,
        fail_run_use_case: FailRunUseCase,
        get_start_step_use_case: GetStartStepUseCase,
        handle_webhook_use_case: HandleWebhookUseCase,
        list_webhooks_use_case: ListWebhooksUseCase,
        register_webhook_use_case: RegisterWebhookUseCase,
        remove_webhook_use_case: RemoveWebhookUseCase,
        resume_run_use_case: ResumeRunUseCase,
        get_run_status_use_case: GetRunStatusUseCase,
        run_worker_service: RunWorkerService,
        handle_input_use_case: HandleInputUseCase | None = None,
    ) -> None:
        self.bootstrap_runtime_use_case = bootstrap_runtime_use_case
        self.append_runtime_event_use_case = append_runtime_event_use_case
        self.create_run_use_case = create_run_use_case
        self.fail_run_use_case = fail_run_use_case
        self.get_start_step_use_case = get_start_step_use_case
        self.handle_input_use_case = handle_input_use_case
        self.handle_webhook_use_case = handle_webhook_use_case
        self.list_webhooks_use_case = list_webhooks_use_case
        self.register_webhook_use_case = register_webhook_use_case
        self.remove_webhook_use_case = remove_webhook_use_case
        self.resume_run_use_case = resume_run_use_case
        self.get_run_status_use_case = get_run_status_use_case
        self.run_worker_service = run_worker_service

    def initialize(self) -> None:
        self.bootstrap_runtime_use_case.initialize()

    def run(
        self,
        skill_ref: str,
        inputs: dict[str, Any],
        *,
        skill_source: str = SkillSource.INTERNAL.value,
    ) -> dict[str, str]:
        created = self.create_run(
            skill_ref,
            inputs,
            skill_source=skill_source,
        )
        run_id = created["run_id"]
        self.prepare_run(run_id)
        self.dispatch_run(run_id)
        return self.get_run_result(run_id)

    def start_worker(self, run_id: str) -> dict[str, str]:
        run = self._get_run_or_raise(run_id)
        if run.status != RunStatus.CREATED.value:
            raise ValueError(f"Run '{run_id}' must be CREATED for worker start")

        self.prepare_run(run_id)
        result = self.get_run_result(run_id)
        start_status = "FAILED" if result["status"] == RunStatus.FAILED.value else "PREPARED"
        return {
            "run_id": run_id,
            "start_status": start_status,
            "status": result["status"],
        }

    def run_worker(self, run_id: str) -> dict[str, str]:
        run = self._get_run_or_raise(run_id)
        blocked_statuses = {
            RunStatus.WAITING.value,
            RunStatus.SUCCEEDED.value,
            RunStatus.FAILED.value,
            RunStatus.CANCELLED.value,
        }
        if run.status in blocked_statuses:
            raise ValueError(f"Run '{run_id}' cannot be executed from status '{run.status}'")
        if run.current is None:
            raise ValueError(f"Run '{run_id}' must be prepared before worker run")

        self.dispatch_run(run_id)
        return self.get_run_result(run_id)

    def create_run(
        self,
        skill_ref: str,
        inputs: dict[str, Any],
        *,
        skill_source: str = SkillSource.INTERNAL.value,
    ) -> dict[str, str]:
        run_id = self.create_run_use_case.execute(
            skill_ref,
            inputs,
            skill_source=skill_source,
        )
        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.RUN_CREATE,
            payload={
                "skill": skill_ref,
                "skill_source": skill_source,
            },
        )
        return {"run_id": run_id, "status": RunStatus.CREATED.value}

    def prepare_run(self, run_id: str) -> None:
        try:
            self.get_start_step_use_case.execute(run_id)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            self.fail_run_use_case.execute(run_id, error=error)
            self.append_runtime_event_use_case.execute(
                run_id,
                event_type=RuntimeEventType.RUN_FINISHED,
                payload={"status": RunStatus.FAILED.value, "error": error},
            )

    def dispatch_run(self, run_id: str) -> None:
        self.run_worker_service.run(run_id)

    def get_run_result(self, run_id: str) -> dict[str, str]:
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
        result = self.handle_webhook_use_case.execute(
            webhook,
            key,
            payload,
            dedup_key=final_dedup_key,
        )
        return {
            "accepted": result.accepted,
            "duplicate": result.duplicate,
            "webhook": webhook,
            "key": key,
            "matched_runs": result.run_ids,
        }

    def handle_input(self, run_id: str, *, text: str) -> dict[str, Any]:
        if self.handle_input_use_case is None:
            raise ValueError("input handling is not configured")
        result = self.handle_input_use_case.execute(run_id, text=text)
        payload = {
            "accepted": result.accepted,
            "run_id": run_id,
            "matched_runs": result.run_ids,
        }
        if result.error is not None:
            payload["error"] = result.error
        return payload

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

    def list_webhooks(self) -> list[dict[str, Any]]:
        result = self.list_webhooks_use_case.execute()
        return result.webhooks

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
            self.append_runtime_event_use_case.execute(
                run_id,
                event_type=RuntimeEventType.RUN_RESUME,
                payload={"source": "manual"},
            )
            self.run_worker_service.run(run_id)
        status_payload = self.get_run_result(run_id)
        return {
            "run_id": run_id,
            "resume_status": result.status.value,
            "status": status_payload["status"],
        }

    def _get_run_or_raise(self, run_id: str) -> Any:
        run = self.get_run_status_use_case.execute(run_id)
        if run is None:
            raise ValueError(f"Run '{run_id}' not found")
        return run
