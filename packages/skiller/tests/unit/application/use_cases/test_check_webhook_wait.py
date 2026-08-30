import pytest

from skiller.application.use_cases.run.check_webhook_wait import (
    CheckWebhookWaitInput,
    CheckWebhookWaitUseCase,
    WebhookWaitConflict,
)
from skiller.domain.step.template_resolution_error import UnresolvedTemplateError
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType

pytestmark = pytest.mark.unit


class _FakeRunner:
    def __init__(self, skill: dict[str, object], render_error: Exception | None = None) -> None:
        self.skill = skill
        self.render_error = render_error

    def load(self, source: str, ref: str) -> dict[str, object]:
        return self.skill

    def render(self, step, context, *, flow):  # noqa: ANN001
        if self.render_error is not None:
            raise self.render_error
        rendered = dict(step)
        rendered["key"] = str(context["inputs"]["key"])
        return rendered


class _FakeWaitStore:
    def __init__(self, waits: list[dict[str, object]]) -> None:
        self.waits = waits
        self.queries: list[dict[str, object]] = []

    def find_matching_waits(self, **query):  # noqa: ANN003
        self.queries.append(query)
        return self.waits


def _use_case(waits: list[dict[str, object]]) -> tuple[CheckWebhookWaitUseCase, _FakeWaitStore]:
    store = _FakeWaitStore(waits)
    runner = _FakeRunner(
        {"steps": [{"wait_webhook": "wait_signal", "webhook": "github", "key": "{{inputs.key}}"}]}
    )
    return CheckWebhookWaitUseCase(store, runner), store


def _request(key: object = 42) -> CheckWebhookWaitInput:
    return CheckWebhookWaitInput(skill_source="internal", skill_ref="skill", inputs={"key": key})


def test_check_webhook_wait_returns_conflict_with_existing_run_id() -> None:
    use_case, store = _use_case([{"run_id": "run-1"}])

    result = use_case.execute(_request())

    assert result.conflict == WebhookWaitConflict(run_id="run-1", webhook="github", key="42")
    assert store.queries[0]["match_key"] == "42"


def test_check_webhook_wait_allows_missing_conflict() -> None:
    use_case, _ = _use_case([])

    result = use_case.execute(_request())

    assert result.conflict is None


def test_check_webhook_wait_ignores_unresolved_template() -> None:
    store = _FakeWaitStore([])
    runner = _FakeRunner(
        {"steps": [{"wait_webhook": "wait_signal", "webhook": "github", "key": "42"}]},
        render_error=UnresolvedTemplateError("not ready"),
    )

    result = CheckWebhookWaitUseCase(store, runner).execute(_request())

    assert result.conflict is None


def test_check_webhook_wait_propagates_render_errors() -> None:
    runner = _FakeRunner(
        {"steps": [{"wait_webhook": "wait_signal", "webhook": "github", "key": "42"}]},
        render_error=ValueError("OUTPUT_VALUE_PATH_MISSING"),
    )

    with pytest.raises(ValueError, match="OUTPUT_VALUE_PATH_MISSING"):
        CheckWebhookWaitUseCase(_FakeWaitStore([]), runner).execute(_request())



def test_check_webhook_wait_uses_webhook_signal_query() -> None:
    use_case, store = _use_case([])

    use_case.execute(_request())

    assert store.queries == [
        {
            "source_type": SourceType.WEBHOOK,
            "source_name": "github",
            "match_type": MatchType.SIGNAL,
            "match_key": "42",
        }
    ]
