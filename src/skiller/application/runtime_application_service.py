from typing import Any

from skiller.application.run_worker_service import RunWorkerService
from skiller.application.use_cases.ingress.handle_channel import HandleChannelUseCase
from skiller.application.use_cases.ingress.handle_input import HandleInputUseCase
from skiller.application.use_cases.ingress.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.query.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.query.list_webhooks import ListWebhooksUseCase
from skiller.application.use_cases.run.append_runtime_event import (
    AppendRuntimeEventUseCase,
    RuntimeEventType,
)
from skiller.application.use_cases.run.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.run.create_run import CreateRunUseCase
from skiller.application.use_cases.run.delete_run import DeleteRunStatus, DeleteRunUseCase
from skiller.application.use_cases.run.fail_run import FailRunUseCase
from skiller.application.use_cases.run.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.run.resume_run import ResumeRunStatus, ResumeRunUseCase
from skiller.application.use_cases.skill.skill_checker import (
    SkillCheckerUseCase,
    SkillCheckStatus,
)
from skiller.application.use_cases.skill.skill_server_checker import (
    SkillServerCheckerUseCase,
    SkillServerCheckStatus,
)
from skiller.application.use_cases.webhook.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.webhook.remove_webhook import (
    RemoveWebhookStatus,
    RemoveWebhookUseCase,
)
from skiller.domain.run.run_model import RunStatus, SkillSource


class RuntimeApplicationService:
    def __init__(
        self,
        bootstrap_runtime_use_case: BootstrapRuntimeUseCase,
        append_runtime_event_use_case: AppendRuntimeEventUseCase,
        create_run_use_case: CreateRunUseCase,
        delete_run_use_case: DeleteRunUseCase,
        fail_run_use_case: FailRunUseCase,
        get_start_step_use_case: GetStartStepUseCase,
        skill_checker_use_case: SkillCheckerUseCase,
        skill_server_checker_use_case: SkillServerCheckerUseCase,
        handle_webhook_use_case: HandleWebhookUseCase,
        list_webhooks_use_case: ListWebhooksUseCase,
        register_webhook_use_case: RegisterWebhookUseCase,
        remove_webhook_use_case: RemoveWebhookUseCase,
        resume_run_use_case: ResumeRunUseCase,
        get_run_status_use_case: GetRunStatusUseCase,
        run_worker_service: RunWorkerService,
        handle_input_use_case: HandleInputUseCase | None = None,
        handle_channel_use_case: HandleChannelUseCase | None = None,
    ) -> None:
        self.bootstrap_runtime_use_case = bootstrap_runtime_use_case
        self.append_runtime_event_use_case = append_runtime_event_use_case
        self.create_run_use_case = create_run_use_case
        self.delete_run_use_case = delete_run_use_case
        self.fail_run_use_case = fail_run_use_case
        self.get_start_step_use_case = get_start_step_use_case
        self.skill_checker_use_case = skill_checker_use_case
        self.skill_server_checker_use_case = skill_server_checker_use_case
        self.handle_input_use_case = handle_input_use_case
        self.handle_webhook_use_case = handle_webhook_use_case
        self.list_webhooks_use_case = list_webhooks_use_case
        self.register_webhook_use_case = register_webhook_use_case
        self.remove_webhook_use_case = remove_webhook_use_case
        self.resume_run_use_case = resume_run_use_case
        self.get_run_status_use_case = get_run_status_use_case
        self.run_worker_service = run_worker_service
        self.handle_channel_use_case = handle_channel_use_case

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
        check_result = self.skill_checker_use_case.execute(skill_ref, skill_source=skill_source)
        if check_result.status == SkillCheckStatus.INVALID:
            messages = [item.message for item in check_result.errors]
            raise ValueError("\n".join(messages))
        server_check_result = self.skill_server_checker_use_case.execute(
            skill_ref,
            skill_source=skill_source,
        )
        if server_check_result.status == SkillServerCheckStatus.INVALID:
            messages = [item.message for item in server_check_result.errors]
            raise ValueError("\n".join(messages))
        run_id = self.create_run_use_case.execute(skill_ref, inputs, skill_source=skill_source)
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

    def delete_run(self, run_id: str) -> dict[str, Any]:
        result = self.delete_run_use_case.execute(run_id)
        payload = {
            "run_id": result.run_id,
            "status": result.status.value,
            "deleted": result.status == DeleteRunStatus.DELETED,
        }
        if result.error is not None:
            payload["error"] = result.error
        return payload

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

    def handle_channel(
        self,
        channel: str,
        key: str,
        payload: dict[str, Any],
        *,
        external_id: str | None = None,
        dedup_key: str | None = None,
    ) -> dict[str, Any]:
        if self.handle_channel_use_case is None:
            raise ValueError("channel handling is not configured")
        final_dedup_key = dedup_key or ""
        result = self.handle_channel_use_case.execute(
            channel,
            key,
            payload,
            external_id=external_id,
            dedup_key=final_dedup_key,
        )
        response = {
            "accepted": result.accepted,
            "duplicate": result.duplicate,
            "channel": channel,
            "key": key,
            "matched_runs": result.run_ids,
        }
        if external_id is not None:
            response["external_id"] = external_id
        if result.error is not None:
            response["error"] = result.error
        return response

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
