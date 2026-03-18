from typing import Any

from skiller.application.query_service import RunQueryService
from skiller.application.runtime_application_service import RuntimeApplicationService
from skiller.domain.run_model import SkillSource


class RuntimeController:
    """Interface adapter: normalizes calls from CLI/HTTP into application services."""

    def __init__(
        self,
        runtime_service: RuntimeApplicationService,
        query_service: RunQueryService,
    ) -> None:
        self.runtime_service = runtime_service
        self.query_service = query_service

    def initialize(self) -> None:
        self.runtime_service.initialize()

    def create_run(
        self,
        skill_ref: str,
        inputs: dict[str, Any],
        *,
        skill_source: str = SkillSource.INTERNAL.value,
    ) -> dict[str, str]:
        return self.runtime_service.create_run(
            skill_ref,
            inputs,
            skill_source=skill_source,
        )

    def start_worker(self, run_id: str) -> dict[str, str]:
        return self.runtime_service.start_worker(run_id)

    def run_worker(self, run_id: str) -> dict[str, str]:
        return self.runtime_service.run_worker(run_id)

    def receive_webhook(
        self,
        webhook: str,
        key: str,
        payload: dict[str, Any],
        dedup_key: str | None = None,
    ) -> dict[str, Any]:
        return self.runtime_service.handle_webhook(webhook, key, payload, dedup_key=dedup_key)

    def receive_input(self, run_id: str, *, text: str) -> dict[str, Any]:
        return self.runtime_service.handle_input(run_id.strip(), text=text.strip())

    def resume(self, run_id: str) -> dict[str, Any]:
        return self.runtime_service.resume_run(run_id)

    def register_webhook(self, webhook: str) -> dict[str, Any]:
        return self.runtime_service.register_webhook(webhook)

    def remove_webhook(self, webhook: str) -> dict[str, Any]:
        return self.runtime_service.remove_webhook(webhook)

    def status(self, run_id: str) -> dict[str, Any] | None:
        return self.query_service.get_status(run_id)

    def logs(self, run_id: str) -> list[dict[str, Any]]:
        return self.query_service.get_logs(run_id)
