import pytest

from skiller.application.use_cases.handle_webhook import HandleWebhookUseCase
from skiller.domain.external_event_type import ExternalEventType

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, *, receipt_is_new: bool = True) -> None:
        self.receipt_is_new = receipt_is_new
        self.created_external_events: list[dict[str, object]] = []
        self.receipts: list[dict[str, object]] = []
        self.waits = [{"run_id": "run-1"}, {"run_id": "run-2"}]

    def register_webhook_receipt(
        self,
        dedup_key: str,
        webhook: str,
        key: str,
        payload: dict[str, object],
    ) -> bool:
        self.receipts.append(
            {
                "dedup_key": dedup_key,
                "webhook": webhook,
                "key": key,
                "payload": payload,
            }
        )
        return self.receipt_is_new

    def create_external_event(
        self,
        *,
        event_type: ExternalEventType,
        payload: dict[str, object],
        run_id: str | None = None,
        step_id: str | None = None,
        webhook: str | None = None,
        key: str | None = None,
        dedup_key: str | None = None,
    ) -> str:
        self.created_external_events.append(
            {
                "event_type": event_type,
                "run_id": run_id,
                "step_id": step_id,
                "webhook": webhook,
                "key": key,
                "dedup_key": dedup_key,
                "payload": payload,
            }
        )
        return "webhook-1"

    def find_matching_waits(self, webhook: str, key: str) -> list[dict[str, object]]:
        _ = (webhook, key)
        return self.waits


def test_handle_webhook_persists_external_event_and_returns_matching_runs() -> None:
    store = _FakeStore()
    use_case = HandleWebhookUseCase(store=store)

    result = use_case.execute(
        "signal",
        "alpha",
        {"price": 123},
        dedup_key="dedup-1",
    )

    assert result.accepted is True
    assert result.duplicate is False
    assert result.run_ids == ["run-1", "run-2"]
    assert result.event_id == "webhook-1"
    assert store.created_external_events == [
        {
            "event_type": ExternalEventType.WEBHOOK,
            "run_id": None,
            "step_id": None,
            "webhook": "signal",
            "key": "alpha",
            "dedup_key": "dedup-1",
            "payload": {"price": 123},
        }
    ]


def test_handle_webhook_skips_external_event_for_duplicate_receipt() -> None:
    store = _FakeStore(receipt_is_new=False)
    use_case = HandleWebhookUseCase(store=store)

    result = use_case.execute(
        "signal",
        "alpha",
        {"price": 123},
        dedup_key="dedup-1",
    )

    assert result.accepted is True
    assert result.duplicate is True
    assert result.run_ids == []
    assert result.event_id is None
    assert store.created_external_events == []
