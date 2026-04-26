import pytest

from skiller.application.use_cases.ingress.handle_webhook import HandleWebhookUseCase
from skiller.domain.match_type import MatchType
from skiller.domain.source_type import SourceType

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, *, receipt_is_new: bool = True) -> None:
        self.receipt_is_new = receipt_is_new
        self.created_external_events: list[dict[str, object]] = []
        self.receipts: list[dict[str, object]] = []
        self.waits = [{"run_id": "run-1"}, {"run_id": "run-2"}]

    def register_external_receipt(
        self,
        dedup_key: str,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        payload: dict[str, object],
    ) -> bool:
        self.receipts.append(
            {
                "dedup_key": dedup_key,
                "source_type": source_type,
                "source_name": source_name,
                "match_type": match_type,
                "match_key": match_key,
                "payload": payload,
            }
        )
        return self.receipt_is_new

    def create_external_event(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        payload: dict[str, object],
        run_id: str | None = None,
        step_id: str | None = None,
        external_id: str | None = None,
        dedup_key: str | None = None,
    ) -> str:
        self.created_external_events.append(
            {
                "source_type": source_type,
                "source_name": source_name,
                "match_type": match_type,
                "match_key": match_key,
                "run_id": run_id,
                "step_id": step_id,
                "external_id": external_id,
                "dedup_key": dedup_key,
                "payload": payload,
            }
        )
        return "webhook-1"

    def find_matching_waits(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
    ) -> list[dict[str, object]]:
        _ = (source_type, source_name, match_type, match_key)
        return self.waits


def test_handle_webhook_persists_external_event_and_returns_matching_runs() -> None:
    store = _FakeStore()
    use_case = HandleWebhookUseCase(external_event_store=store, wait_store=store)

    result = use_case.execute(
        "signal",
        "alpha",
        {"price": 123},
        dedup_key="dedup-1",
    )

    assert result.accepted is True
    assert result.duplicate is False
    assert result.run_ids == ["run-1"]
    assert result.event_id == "webhook-1"
    assert store.created_external_events == [
        {
            "source_type": SourceType.WEBHOOK,
            "source_name": "signal",
            "match_type": MatchType.SIGNAL,
            "match_key": "alpha",
            "run_id": None,
            "step_id": None,
            "external_id": None,
            "dedup_key": "dedup-1",
            "payload": {"price": 123},
        }
    ]


def test_handle_webhook_selects_only_first_matching_run() -> None:
    store = _FakeStore()
    use_case = HandleWebhookUseCase(external_event_store=store, wait_store=store)

    result = use_case.execute(
        "signal",
        "alpha",
        {"price": 123},
        dedup_key="dedup-1",
    )

    assert result.run_ids == ["run-1"]


def test_handle_webhook_skips_external_event_for_duplicate_receipt() -> None:
    store = _FakeStore(receipt_is_new=False)
    use_case = HandleWebhookUseCase(external_event_store=store, wait_store=store)

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
