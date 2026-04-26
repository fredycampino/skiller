import pytest

from skiller.application.use_cases.query.get_runs import GetRunsUseCase
from skiller.domain.run_list_item_model import RunListItem

pytestmark = pytest.mark.unit


class _FakeRunQueryStore:
    def __init__(self, runs: list[RunListItem]) -> None:
        self.runs = runs
        self.calls: list[tuple[int, list[str] | None]] = []

    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[RunListItem]:
        self.calls.append((limit, statuses))
        return list(self.runs)


def test_get_runs_returns_minimal_payload_and_wait_detail() -> None:
    query_store = _FakeRunQueryStore(
        [
            RunListItem(
                id="f25d21cc-95ea-4dc1-9305-c18f4ddceaca",
                skill_source="internal",
                skill_ref="chat",
                status="WAITING",
                current="ask_user",
                created_at="2026-03-30 10:00:00",
                updated_at="2026-03-30 10:01:00",
                wait_type="input",
            ),
            RunListItem(
                id="eeee1234-1111-2222-3333-444444444444",
                skill_source="internal",
                skill_ref="repo_checks",
                status="SUCCEEDED",
                current="summarize",
                created_at="2026-03-30 09:00:00",
                updated_at="2026-03-30 09:05:00",
            ),
        ]
    )
    use_case = GetRunsUseCase(query_store)

    result = use_case.execute(limit=10, statuses=["WAITING", "SUCCEEDED"])

    assert query_store.calls == [(10, ["WAITING", "SUCCEEDED"])]
    assert [item.id for item in result] == [
        "f25d21cc-95ea-4dc1-9305-c18f4ddceaca",
        "eeee1234-1111-2222-3333-444444444444",
    ]
    assert result[0].to_dict() == {
        "id": "f25d21cc-95ea-4dc1-9305-c18f4ddceaca",
        "skill_source": "internal",
        "skill_ref": "chat",
        "status": "WAITING",
        "current": "ask_user",
        "created_at": "2026-03-30 10:00:00",
        "updated_at": "2026-03-30 10:01:00",
        "wait_type": "input",
    }
    assert result[1].to_dict() == {
        "id": "eeee1234-1111-2222-3333-444444444444",
        "skill_source": "internal",
        "skill_ref": "repo_checks",
        "status": "SUCCEEDED",
        "current": "summarize",
        "created_at": "2026-03-30 09:00:00",
        "updated_at": "2026-03-30 09:05:00",
    }
