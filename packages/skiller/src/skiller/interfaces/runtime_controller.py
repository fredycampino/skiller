from typing import Any

from skiller.application.agents.mapper import AgentServiceMapper
from skiller.application.agents.service import AgentApplicationService
from skiller.application.query_service import RunQueryService
from skiller.application.runs.mapper import RunServiceMapper
from skiller.application.runs.service import RunApplicationService
from skiller.application.waits.channel_mapper import ChannelWaitMapper
from skiller.application.waits.input_mapper import InputWaitMapper
from skiller.application.waits.service import WaitApplicationService
from skiller.application.waits.webhook_mapper import WebhookWaitMapper
from skiller.domain.run.run_model import SkillSource


class RuntimeController:
    """Interface adapter: normalizes calls from CLI/HTTP into application services."""

    def __init__(
        self,
        agent_service: AgentApplicationService,
        agent_mapper: AgentServiceMapper,
        run_service: RunApplicationService,
        run_mapper: RunServiceMapper,
        query_service: RunQueryService,
        wait_service: WaitApplicationService,
        input_wait_mapper: InputWaitMapper,
        channel_wait_mapper: ChannelWaitMapper,
        webhook_wait_mapper: WebhookWaitMapper,
    ) -> None:
        self.agent_service = agent_service
        self.agent_mapper = agent_mapper
        self.run_service = run_service
        self.run_mapper = run_mapper
        self.query_service = query_service
        self.wait_service = wait_service
        self.input_wait_mapper = input_wait_mapper
        self.channel_wait_mapper = channel_wait_mapper
        self.webhook_wait_mapper = webhook_wait_mapper

    def initialize(self) -> None:
        self.run_service.initialize()

    def create_run(
        self,
        skill_ref: str,
        inputs: dict[str, Any],
        *,
        skill_source: str = SkillSource.INTERNAL.value,
    ) -> dict[str, str]:
        request = self.run_mapper.to_create_input(
            skill_ref,
            inputs,
            skill_source=skill_source,
        )
        result = self.run_service.create_run(request)
        return self.run_mapper.to_run_dict(result)

    def start_worker(self, run_id: str) -> dict[str, str]:
        result = self.run_service.start_worker(run_id.strip())
        return self.run_mapper.to_worker_start_dict(result)

    def run_worker(self, run_id: str) -> dict[str, str]:
        result = self.run_service.run_worker(run_id.strip())
        return self.run_mapper.to_run_dict(result)

    def receive_webhook(
        self,
        webhook: str,
        key: str,
        payload: dict[str, Any],
        dedup_key: str | None = None,
    ) -> dict[str, Any]:
        request = self.webhook_wait_mapper.to_handle_input(webhook, key, payload, dedup_key)
        result = self.wait_service.handle_webhook(request)
        return self.webhook_wait_mapper.to_handle_dict(request, result)

    def receive_input(self, run_id: str, *, text: str) -> dict[str, Any]:
        request = self.input_wait_mapper.to_handle_input(run_id, text=text)
        result = self.wait_service.handle_input(request)
        return self.input_wait_mapper.to_handle_dict(request, result)

    def receive_channel(
        self,
        channel: str,
        key: str,
        payload: dict[str, Any],
        *,
        external_id: str | None = None,
        dedup_key: str | None = None,
    ) -> dict[str, Any]:
        request = self.channel_wait_mapper.to_handle_input(
            channel,
            key,
            payload,
            external_id=external_id,
            dedup_key=dedup_key,
        )
        result = self.wait_service.handle_channel(request)
        return self.channel_wait_mapper.to_handle_dict(request, result)

    def resume(self, run_id: str) -> dict[str, Any]:
        result = self.run_service.resume_run(run_id.strip())
        return self.run_mapper.to_resume_dict(result)

    def interrupt_agent(self, run_id: str) -> dict[str, Any]:
        request = self.agent_mapper.to_interrupt_input(run_id)
        result = self.agent_service.interrupt_agent(request)
        return self.agent_mapper.to_interrupt_dict(result)

    def agent_stats(self, run_id: str, agent_id: str) -> dict[str, Any]:
        final_run_id, final_agent_id = self.agent_mapper.to_stats_input(run_id, agent_id)
        result = self.agent_service.get_agent_stats(final_run_id, final_agent_id)
        return self.agent_mapper.to_stats_dict(result)

    def delete_run(self, run_id: str) -> dict[str, Any]:
        result = self.run_service.delete_run(run_id.strip())
        return self.run_mapper.to_delete_dict(result)

    def action_done(self, run_id: str, step_id: str) -> dict[str, Any]:
        request = self.run_mapper.to_action_done_input(run_id, step_id)
        result = self.run_service.mark_notify_action_done(
            request,
        )
        return self.run_mapper.to_action_done_dict(result)

    def register_webhook(
        self,
        webhook: str,
        *,
        method: str = "POST",
        auth: str = "signed",
        payload_source: str = "body_json",
    ) -> dict[str, Any]:
        try:
            request = self.webhook_wait_mapper.to_register_input(
                webhook,
                method=method,
                auth=auth,
                payload_source=payload_source,
            )
        except ValueError as exc:
            return self.webhook_wait_mapper.to_register_error_dict(webhook, str(exc))
        result = self.wait_service.register_webhook(request)
        return self.webhook_wait_mapper.to_register_dict(result)

    def list_webhooks(self) -> list[dict[str, Any]]:
        result = self.wait_service.list_webhooks()
        return self.webhook_wait_mapper.to_list_dict(result)

    def remove_webhook(self, webhook: str) -> dict[str, Any]:
        request = self.webhook_wait_mapper.to_remove_input(webhook)
        result = self.wait_service.remove_webhook(request)
        return self.webhook_wait_mapper.to_remove_dict(result)

    def status(
        self,
        run_id: str,
        *,
        include_context: bool = False,
    ) -> dict[str, Any] | None:
        return self.query_service.get_status(run_id, include_context=include_context)

    def logs(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.query_service.get_logs(
            run_id,
            after_sequence=after_sequence,
            limit=limit,
        )

    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self.query_service.list_runs(limit=limit, statuses=statuses)
