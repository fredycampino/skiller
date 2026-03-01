from typing import Any
import uuid

from runtime.domain.models import Event


class HandleWebhookUseCase:
    def execute(self, wait_key: str, payload: dict[str, Any]) -> Event:
        return Event(
            event_id=str(uuid.uuid4()),
            event_type="WEBHOOK_RECEIVED",
            payload={"key": wait_key, "payload": payload},
            run_id=None,
        )
