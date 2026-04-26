from skiller.application.ports.external_event_store_port import ExternalEventStorePort
from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.ports.wait_store_port import WaitStorePort
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.application.use_cases.shared.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.step_execution_model import StepExecution, WaitWebhookOutput
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType
from skiller.domain.wait.wait_type import WaitType


class ExecuteWaitWebhookStepUseCase:
    def __init__(
        self,
        run_store: RunStorePort,
        wait_store: WaitStorePort,
        external_event_store: ExternalEventStorePort,
    ) -> None:
        self.run_store = run_store
        self.wait_store = wait_store
        self.external_event_store = external_event_store

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step = current_step.step
        step_id = current_step.step_id
        webhook = str(step.get("webhook", "")).strip()
        key = str(step.get("key", "")).strip()

        if not webhook:
            raise ValueError(f"Step '{step_id}' requires webhook")
        if not key:
            raise ValueError(f"Step '{step_id}' requires key")

        active_wait = self.wait_store.get_active_wait(
            current_step.run_id,
            step_id,
            wait_type=WaitType.WEBHOOK,
        )
        webhook_event = self.external_event_store.get_latest_external_event(
            source_type=SourceType.WEBHOOK,
            source_name=webhook,
            match_type=MatchType.SIGNAL,
            match_key=key,
            since_created_at=current_step.run_created_at,
        )

        if webhook_event is not None:
            webhook_event_id = str(webhook_event.get("id", "")).strip()
            if not webhook_event_id:
                webhook_event = None
            elif not self.external_event_store.consume_external_event(
                webhook_event_id,
                run_id=current_step.run_id,
            ):
                webhook_event = None

        if webhook_event is not None:
            payload = webhook_event.get("payload")
            if not isinstance(payload, dict):
                payload = None
            execution = StepExecution(
                step_type=current_step.step_type,
                input={"webhook": webhook, "key": key},
                evaluation={},
                output=WaitWebhookOutput(
                    text=f"Webhook received: {webhook}:{key}.",
                    webhook=webhook,
                    key=key,
                    payload=payload,
                ),
            )
            current_step.context.step_executions[step_id] = execution
            if active_wait is not None:
                self.wait_store.resolve_wait(str(active_wait["id"]))

            raw_next = step.get("next")
            if raw_next is None:
                self.run_store.update_run(
                    current_step.run_id,
                    status=RunStatus.RUNNING,
                    context=current_step.context,
                )
                return StepAdvance(
                    status=StepExecutionStatus.COMPLETED,
                    execution=execution,
                )

            next_step_id = str(raw_next).strip()
            if not next_step_id:
                raise ValueError(f"Step '{step_id}' requires non-empty next")

            self.run_store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                current=next_step_id,
                context=current_step.context,
            )
            return StepAdvance(
                status=StepExecutionStatus.NEXT,
                next_step_id=next_step_id,
                execution=execution,
            )

        if active_wait is None:
            self.wait_store.create_wait(
                current_step.run_id,
                step_id=step_id,
                wait_type=WaitType.WEBHOOK,
                source_type=SourceType.WEBHOOK,
                source_name=webhook,
                match_type=MatchType.SIGNAL,
                match_key=key,
            )
        self.run_store.update_run(
            current_step.run_id,
            status=RunStatus.WAITING,
            current=step_id,
            context=current_step.context,
        )
        return StepAdvance(
            status=StepExecutionStatus.WAITING,
            execution=StepExecution(
                step_type=current_step.step_type,
                input={"webhook": webhook, "key": key},
                evaluation={},
                output=WaitWebhookOutput(
                    text=f"Waiting webhook: {webhook}:{key}.",
                    webhook=webhook,
                    key=key,
                ),
            ),
        )
