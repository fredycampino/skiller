from types import SimpleNamespace

import pytest

from skiller.application.agents.mapper import AgentServiceMapper
from skiller.application.query_mapper import RunStatusMapper
from skiller.application.runs.mapper import RunServiceMapper
from skiller.application.runs.models import RunResult
from skiller.application.use_cases.agent.list_agent_models import (
    AgentModelItem,
    AgentModelsProviderItem,
    ListAgentModelsResult,
    ListAgentModelsStatus,
)
from skiller.application.use_cases.agent.select_agent_model import (
    SelectAgentModelResult,
    SelectAgentModelStatus,
)
from skiller.application.use_cases.ingress.handle_webhook import HandleWebhookResult
from skiller.application.use_cases.run.mark_notify_action_done import (
    MarkNotifyActionDoneResult,
    MarkNotifyActionDoneStatus,
)
from skiller.application.use_cases.webhook.register_webhook import (
    RegisterWebhookResult,
    RegisterWebhookStatus,
)
from skiller.application.waits.channel_mapper import ChannelWaitMapper
from skiller.application.waits.input_mapper import InputWaitMapper
from skiller.application.waits.webhook_mapper import WebhookWaitMapper
from skiller.domain.agent.config.port import AgentConfigProviderSource
from skiller.domain.event.event_model import RuntimeEventType
from skiller.domain.event.webhook_registration_model import (
    WebhookAuth,
    WebhookMethod,
    WebhookPayloadSource,
)
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_status_runtime_model import RunStatusRuntime
from skiller.interfaces.runtime_controller import RuntimeController

pytestmark = pytest.mark.unit


class _FakeAgentService:
    def __init__(self) -> None:
        self.models_run_id = ""
        self.select_model_call: dict[str, str] | None = None

    def list_agent_models(self, run_id: str) -> ListAgentModelsResult:
        self.models_run_id = run_id
        return ListAgentModelsResult(
            status=ListAgentModelsStatus.OK,
            run_id=run_id,
            providers=(
                AgentModelsProviderItem(
                    name="codex",
                    source=AgentConfigProviderSource.GLOBAL,
                    models=(AgentModelItem(name="gpt-5.5", active=True),),
                ),
            ),
        )

    def select_agent_model(
        self,
        *,
        run_id: str,
        provider: str,
        model: str,
    ) -> SelectAgentModelResult:
        self.select_model_call = {
            "run_id": run_id,
            "provider": provider,
            "model": model,
        }
        return SelectAgentModelResult(
            status=SelectAgentModelStatus.OK,
            run_id=run_id,
            provider=provider,
            model=model,
        )


class _FakeRunService:
    def __init__(self) -> None:
        self.create_request = None
        self.mark_action_call = None

    def initialize(self) -> None:
        pass

    def create_run(self, request):  # noqa: ANN001, ANN201
        self.create_request = request
        return RunResult(run_id="run-1", status=RunStatus.CREATED)

    def mark_notify_action_done(self, request):  # noqa: ANN001, ANN201
        self.mark_action_call = request
        return MarkNotifyActionDoneResult(
            run_id=request.run_id,
            action_uid=request.action_uid,
            status=MarkNotifyActionDoneStatus.DONE,
            changed=True,
            step_id="auth_link",
        )


class _FakeWaitService:
    def __init__(self) -> None:
        self.register_request = None
        self.handle_request = None

    def register_webhook(self, request):  # noqa: ANN001, ANN201
        self.register_request = request
        return RegisterWebhookResult(
            status=RegisterWebhookStatus.REGISTERED,
            webhook=request.webhook,
            method=request.method,
            auth=request.auth,
            payload_source=request.payload_source,
            secret="secret-1",
            enabled=True,
        )

    def handle_webhook(self, request):  # noqa: ANN001, ANN201
        self.handle_request = request
        return HandleWebhookResult(
            accepted=True,
            duplicate=False,
            run_ids=["run-1"],
        )


class _FakeQueryService:
    def __init__(self) -> None:
        self.status_calls: list[str] = []

    def get_status(self, run_id: str) -> RunStatusRuntime:
        self.status_calls.append(run_id)
        return RunStatusRuntime(
            run_id=run_id,
            status=RunStatus.WAITING,
            wait_type="input",
            prompt="Write a message",
            last_event_sequence=42,
            last_event_type=RuntimeEventType.RUN_WAITING,
        )


def _controller(
    wait_service: _FakeWaitService,
    run_service: _FakeRunService | None = None,
    query_service: _FakeQueryService | None = None,
    agent_service: _FakeAgentService | None = None,
) -> RuntimeController:
    final_run_service = run_service or _FakeRunService()
    return RuntimeController(
        agent_service=agent_service or _FakeAgentService(),
        agent_mapper=AgentServiceMapper(),
        run_service=final_run_service,
        run_mapper=RunServiceMapper(),
        query_service=query_service or SimpleNamespace(),
        status_mapper=RunStatusMapper(),
        wait_service=wait_service,
        input_wait_mapper=InputWaitMapper(),
        channel_wait_mapper=ChannelWaitMapper(),
        webhook_wait_mapper=WebhookWaitMapper(),
    )


def test_controller_maps_status_result_to_public_dict() -> None:
    query_service = _FakeQueryService()
    controller = _controller(_FakeWaitService(), query_service=query_service)

    result = controller.status(" run-1 ")

    assert query_service.status_calls == ["run-1"]
    assert result == {
        "run_id": "run-1",
        "status": "WAITING",
        "wait_type": "input",
        "prompt": "Write a message",
        "last_event_sequence": 42,
        "last_event_type": "RUN_WAITING",
    }


def test_controller_maps_create_run_to_typed_service_input() -> None:
    run_service = _FakeRunService()
    controller = _controller(_FakeWaitService(), run_service=run_service)

    result = controller.create_run(
        " notify_test ",
        {"message": "ok"},
        skill_source="internal",
    )

    assert run_service.create_request.skill_ref == "notify_test"
    assert run_service.create_request.inputs == {"message": "ok"}
    assert run_service.create_request.skill_source == "internal"
    assert result == {"run_id": "run-1", "status": "CREATED"}


def test_controller_maps_agent_models_to_agent_service() -> None:
    agent_service = _FakeAgentService()
    controller = _controller(_FakeWaitService(), agent_service=agent_service)

    result = controller.agent_models(" run-1 ")

    assert agent_service.models_run_id == "run-1"
    assert result == {
        "run_id": "run-1",
        "status": "OK",
        "ok": True,
        "providers": [
            {
                "name": "codex",
                "source": "global",
                "models": [{"name": "gpt-5.5", "active": True}],
            },
        ],
    }


def test_controller_maps_agent_model_to_agent_service() -> None:
    agent_service = _FakeAgentService()
    controller = _controller(_FakeWaitService(), agent_service=agent_service)

    result = controller.agent_model(" run-1 ", " codex ", " gpt-5.4 ")

    assert agent_service.select_model_call == {
        "run_id": "run-1",
        "provider": "codex",
        "model": "gpt-5.4",
    }
    assert result == {
        "run_id": "run-1",
        "provider": "codex",
        "model": "gpt-5.4",
        "status": "OK",
        "ok": True,
    }


def test_controller_maps_action_done_to_run_service() -> None:
    run_service = _FakeRunService()
    controller = _controller(_FakeWaitService(), run_service=run_service)

    result = controller.action_done(" run-1 ", " action-1 ")

    assert run_service.mark_action_call.run_id == "run-1"
    assert run_service.mark_action_call.action_uid == "action-1"
    assert result == {
        "run_id": "run-1",
        "action_uid": "action-1",
        "step_id": "auth_link",
        "status": "DONE",
        "done": True,
        "changed": True,
    }


def test_controller_maps_register_webhook_to_typed_service_input() -> None:
    wait_service = _FakeWaitService()
    controller = _controller(wait_service)

    result = controller.register_webhook(
        " example-auth ",
        method="get",
        auth="none",
        payload_source="query",
    )

    assert wait_service.register_request.webhook == "example-auth"
    assert wait_service.register_request.method == WebhookMethod.GET
    assert wait_service.register_request.auth == WebhookAuth.NONE
    assert wait_service.register_request.payload_source == WebhookPayloadSource.QUERY
    assert result == {
        "webhook": "example-auth",
        "status": "REGISTERED",
        "method": "GET",
        "auth": "none",
        "payload_source": "query",
        "secret": "secret-1",
        "enabled": True,
    }


def test_controller_rejects_invalid_register_webhook_params_before_service() -> None:
    wait_service = _FakeWaitService()
    controller = _controller(wait_service)

    result = controller.register_webhook(
        "example-auth",
        method="GET",
        auth="none",
        payload_source="body_json",
    )

    assert wait_service.register_request is None
    assert result == {
        "webhook": "example-auth",
        "status": "INVALID_CONFIG",
        "error": "webhook method and payload source must be POST/body_json or GET/query",
    }


def test_controller_maps_receive_webhook_to_typed_service_input() -> None:
    wait_service = _FakeWaitService()
    controller = _controller(wait_service)

    result = controller.receive_webhook(
        " github ",
        " 42 ",
        {"ok": True},
        dedup_key=" delivery-1 ",
    )

    assert wait_service.handle_request.webhook == "github"
    assert wait_service.handle_request.key == "42"
    assert wait_service.handle_request.payload == {"ok": True}
    assert wait_service.handle_request.dedup_key == "delivery-1"
    assert result == {
        "accepted": True,
        "duplicate": False,
        "webhook": "github",
        "key": "42",
        "matched_runs": ["run-1"],
    }
