import pytest

from skiller.application.action.action_uid_factory import ActionUidFactory
from skiller.application.use_cases.run.resolve_end_action import (
    ResolveEndActionInput,
    ResolveEndActionUseCase,
)
from skiller.application.use_cases.run.resolve_end_action_config import (
    ResolveEndActionConfigParser,
)
from skiller.domain.action.action_model import EndActionTrigger, PostAction, RunAction
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunStatus

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run

    def get_run(self, run_id: str) -> Run | None:
        if self.run is None or self.run.id != run_id:
            return None
        return self.run


class _FakeRunner:
    def __init__(self) -> None:
        self.render_calls: list[dict[str, object]] = []

    def render(self, step, context, *, flow):  # noqa: ANN001, ANN201
        self.render_calls.append(
            {
                "step": step,
                "context": context,
                "flow": flow,
            }
        )
        rendered = dict(step)
        inputs = context.get("inputs", {})
        if isinstance(inputs, dict):
            for key, value in inputs.items():
                token = "{{inputs." + str(key) + "}}"
                for field, raw in rendered.items():
                    if isinstance(raw, str):
                        rendered[field] = raw.replace(token, str(value))
        return rendered


class _FakeActionUidFactory(ActionUidFactory):
    def new_uid(self) -> str:
        return "end-action-uid"


def _config_parser() -> ResolveEndActionConfigParser:
    return ResolveEndActionConfigParser(_FakeRunner(), _FakeActionUidFactory())


def _config_parser_with_runner() -> tuple[ResolveEndActionConfigParser, _FakeRunner]:
    runner = _FakeRunner()
    return ResolveEndActionConfigParser(runner, _FakeActionUidFactory()), runner


def test_resolve_end_action_returns_on_success_run_action() -> None:
    run = _build_run(
        {
            "on_success": {
                "action": {
                    "type": "run",
                    "label": "Open result",
                    "arg": "--file {{inputs.flow}}",
                    "params": "--id {{inputs.run_key}}",
                    "auto": True,
                }
            }
        }
    )
    config_parser, runner = _config_parser_with_runner()
    use_case = ResolveEndActionUseCase(
        store=_FakeStore(run),
        config_parser=config_parser,
    )

    result = use_case.execute(
        ResolveEndActionInput(run_id="run-1", trigger=EndActionTrigger.ON_SUCCESS)
    )

    assert result.action == RunAction(
        uid="end-action-uid",
        label="Open result",
        arg="--file ./flows/result.yaml",
        params="--id abc",
        auto=True,
    )
    assert runner.render_calls[0]["flow"] is run


def test_resolve_end_action_returns_on_success_post_action() -> None:
    run = _build_run(
        {
            "on_success": {
                "action": {
                    "type": "post",
                    "label": "Auth success",
                    "arg": "load_session",
                    "params": "run_id={{inputs.run_key}}",
                    "auto": True,
                }
            }
        }
    )
    config_parser, runner = _config_parser_with_runner()
    use_case = ResolveEndActionUseCase(
        store=_FakeStore(run),
        config_parser=config_parser,
    )

    result = use_case.execute(
        ResolveEndActionInput(run_id="run-1", trigger=EndActionTrigger.ON_SUCCESS)
    )

    assert result.action == PostAction(
        uid="end-action-uid",
        label="Auth success",
        arg="load_session",
        params="run_id=abc",
        auto=True,
    )
    assert runner.render_calls[0]["flow"] is run


def test_resolve_end_action_returns_on_error_run_action() -> None:
    run = _build_run(
        {
            "on_error": {
                "action": {
                    "type": "run",
                    "label": "Debug failure",
                    "arg": "--file ./flows/debug.yaml",
                    "params": "--val pepe",
                    "auto": True,
                }
            }
        }
    )
    config_parser, runner = _config_parser_with_runner()
    use_case = ResolveEndActionUseCase(
        store=_FakeStore(run),
        config_parser=config_parser,
    )

    result = use_case.execute(
        ResolveEndActionInput(run_id="run-1", trigger=EndActionTrigger.ON_ERROR)
    )

    assert result.action == RunAction(
        uid="end-action-uid",
        label="Debug failure",
        arg="--file ./flows/debug.yaml",
        params="--val pepe",
        auto=True,
    )
    assert runner.render_calls[0]["flow"] is run


def test_resolve_end_action_ignores_open_url_action() -> None:
    run = _build_run(
        {
            "on_success": {
                "action": {
                    "type": "open_url",
                    "label": "Open",
                    "url": "https://example.com",
                }
            }
        }
    )
    use_case = ResolveEndActionUseCase(
        store=_FakeStore(run),
        config_parser=_config_parser(),
    )

    result = use_case.execute(
        ResolveEndActionInput(run_id="run-1", trigger=EndActionTrigger.ON_SUCCESS)
    )

    assert result.action is None


def test_resolve_end_action_ignores_missing_or_invalid_action() -> None:
    run = _build_run({"on_success": {"action": {"type": "run", "label": "Debug"}}})
    use_case = ResolveEndActionUseCase(
        store=_FakeStore(run),
        config_parser=_config_parser(),
    )

    result = use_case.execute(
        ResolveEndActionInput(run_id="run-1", trigger=EndActionTrigger.ON_SUCCESS)
    )

    assert result.action is None


def test_resolve_end_action_ignores_missing_run() -> None:
    use_case = ResolveEndActionUseCase(
        store=_FakeStore(None),
        config_parser=_config_parser(),
    )

    result = use_case.execute(
        ResolveEndActionInput(run_id="missing", trigger=EndActionTrigger.ON_SUCCESS)
    )

    assert result.action is None


def _build_run(snapshot: dict[str, object]) -> Run:
    return Run(
        id="run-1",
        source="internal",
        ref="test",
        snapshot=snapshot,
        status=RunStatus.SUCCEEDED.value,
        current=None,
        context=RunContext(
            inputs={
                "flow": "./flows/result.yaml",
                "run_key": "abc",
            },
            step_executions={},
        ),
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
