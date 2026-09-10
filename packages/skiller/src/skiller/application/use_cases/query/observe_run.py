from collections.abc import Iterator

from skiller.application.observations.errors import ObserveRunError
from skiller.application.observations.models import (
    ObserveEvent,
    ObserveIdle,
    ObserveRunInput,
    ObserveRunResult,
    ObserveRunSettings,
    ObserveStart,
    ObserveStop,
    ObserveWait,
    ObserveWaitType,
)
from skiller.application.waits.waiting_metadata_resolver import (
    InputWaitingMetadata,
    WaitingMetadataResolver,
    WebhookWaitingMetadata,
)
from skiller.domain.event.event_model import RuntimeEvent, RuntimeEventType
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_store_port import RunStorePort

_TERMINAL_STATUSES = {
    RunStatus.SUCCEEDED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
}


class ObserveRunUseCase:
    def __init__(
        self,
        *,
        run_store: RunStorePort,
        event_store: RuntimeEventStorePort,
        waiting_metadata_resolver: WaitingMetadataResolver,
        settings: ObserveRunSettings,
    ) -> None:
        self.run_store = run_store
        self.event_store = event_store
        self.waiting_metadata_resolver = waiting_metadata_resolver
        self.settings = settings

    def execute(self, request: ObserveRunInput) -> Iterator[ObserveRunResult]:
        initial_status = self.run_store.get_status(request.run_id)
        if initial_status is None:
            raise ObserveRunError(f"Run '{request.run_id}' not found")

        initial_last_event = self.event_store.get_last_event(request.run_id)
        initial_last_sequence = self._event_sequence(initial_last_event)
        requested_cursor = request.after if request.after is not None else 0
        if requested_cursor > initial_last_sequence:
            raise ObserveRunError(
                f"--after {requested_cursor} exceeds last sequence {initial_last_sequence}"
            )

        effective_after = max(requested_cursor, initial_last_sequence - request.tail)
        yield ObserveStart(
            run_id=request.run_id,
            requested_after=request.after,
            effective_after=effective_after,
            last_sequence=initial_last_sequence,
            tail=request.tail,
            truncated=effective_after > requested_cursor,
        )

        cursor = effective_after
        emitted_wait_sequence: int | None = None
        evaluated_cursor: int | None = None

        while True:
            events = self.event_store.list_events(
                request.run_id,
                after_sequence=cursor,
                limit=self.settings.batch_size,
            )
            if events:
                for event in events:
                    sequence = self._validated_sequence(event, cursor=cursor)
                    yield ObserveEvent(event=event)
                    cursor = sequence
                continue

            if evaluated_cursor == cursor:
                yield ObserveIdle()
                continue

            last_event = self.event_store.get_last_event(request.run_id)
            last_sequence = self._event_sequence(last_event)
            if last_sequence > cursor:
                continue
            if last_sequence < cursor:
                raise ObserveRunError("last persisted event sequence is behind the observed cursor")

            status = self.run_store.get_status(request.run_id)
            if status is None:
                raise ObserveRunError(f"Run '{request.run_id}' not found")
            if status.status in _TERMINAL_STATUSES:
                if last_event is None or last_event.type != RuntimeEventType.RUN_FINISHED:
                    evaluated_cursor = cursor
                    yield ObserveIdle()
                    continue
                yield ObserveStop(sequence=cursor, status=status.status)
                return

            waiting = self._waiting_result(
                run_id=request.run_id,
                cursor=cursor,
                last_event=last_event,
            )
            evaluated_cursor = cursor
            if waiting is not None and waiting.sequence != emitted_wait_sequence:
                emitted_wait_sequence = waiting.sequence
                yield waiting
                continue

            yield ObserveIdle()

    def _validated_sequence(self, event: RuntimeEvent, *, cursor: int) -> int:
        sequence = event.sequence
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            raise ObserveRunError("event sequence must be an integer")
        if sequence <= cursor:
            raise ObserveRunError("event sequence must increase monotonically")
        return sequence

    def _event_sequence(self, event: RuntimeEvent | None) -> int:
        if event is None:
            return 0
        sequence = event.sequence
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise ObserveRunError("event sequence must be a non-negative integer")
        return sequence

    def _waiting_result(
        self,
        *,
        run_id: str,
        cursor: int,
        last_event: RuntimeEvent | None,
    ) -> ObserveWait | None:
        if last_event is None or last_event.type != RuntimeEventType.RUN_WAITING:
            return None

        run = self.run_store.get_run(run_id)
        if run is None:
            return None

        metadata = self.waiting_metadata_resolver.resolve(run)
        if isinstance(metadata, InputWaitingMetadata):
            return ObserveWait(
                sequence=cursor,
                wait_type=ObserveWaitType.INPUT,
                prompt=metadata.prompt,
            )
        if isinstance(metadata, WebhookWaitingMetadata):
            return ObserveWait(
                sequence=cursor,
                wait_type=ObserveWaitType.WEBHOOK,
            )
        return None
