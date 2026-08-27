import pytest

from skiller.application.use_cases.ingress.handle_webhook import HandleWebhookResult
from skiller.application.use_cases.query.list_webhooks import ListWebhooksResult
from skiller.application.use_cases.webhook.register_webhook import (
    RegisterWebhookResult,
    RegisterWebhookStatus,
)
from skiller.application.use_cases.webhook.remove_webhook import (
    RemoveWebhookResult,
    RemoveWebhookStatus,
)
from skiller.application.waits.webhook_mapper import (
    WEBHOOK_CONFIG_ERROR,
    WebhookWaitMapper,
)
from skiller.domain.event.webhook_registration_model import (
    WebhookAuth,
    WebhookMethod,
    WebhookPayloadSource,
    WebhookRegistration,
)

pytestmark = pytest.mark.unit


def test_mapper_builds_handle_webhook_input_and_output() -> None:
    mapper = WebhookWaitMapper()

    request = mapper.to_handle_input(
        " github ",
        " 42 ",
        {"ok": True},
        " delivery-1 ",
    )
    result = HandleWebhookResult(
        accepted=True,
        duplicate=False,
        run_ids=["run-1"],
    )

    assert request.webhook == "github"
    assert request.key == "42"
    assert request.payload == {"ok": True}
    assert request.dedup_key == "delivery-1"
    assert mapper.to_handle_dict(request, result) == {
        "accepted": True,
        "duplicate": False,
        "webhook": "github",
        "key": "42",
        "matched_runs": ["run-1"],
    }


def test_mapper_builds_register_webhook_input() -> None:
    mapper = WebhookWaitMapper()

    request = mapper.to_register_input(
        " example-auth ",
        method="get",
        auth=" none ",
        payload_source=" query ",
        token_header=None,
    )

    assert request.webhook == "example-auth"
    assert request.method == WebhookMethod.GET
    assert request.auth == WebhookAuth.NONE
    assert request.payload_source == WebhookPayloadSource.QUERY


def test_mapper_rejects_invalid_register_webhook_options() -> None:
    mapper = WebhookWaitMapper()

    with pytest.raises(ValueError, match=WEBHOOK_CONFIG_ERROR):
        mapper.to_register_input(
            "example-auth",
            method="GET",
            auth="none",
            payload_source="body_json",
            token_header=None,
        )

    assert mapper.to_register_error_dict("example-auth", WEBHOOK_CONFIG_ERROR) == {
        "webhook": "example-auth",
        "status": "INVALID_CONFIG",
        "error": WEBHOOK_CONFIG_ERROR,
    }


def test_mapper_serializes_register_webhook_result() -> None:
    mapper = WebhookWaitMapper()
    result = RegisterWebhookResult(
        status=RegisterWebhookStatus.REGISTERED,
        webhook="github-ci",
        method=WebhookMethod.POST,
        auth=WebhookAuth.SIGNED,
        payload_source=WebhookPayloadSource.BODY_JSON,
        token_header=None,
        secret="secret-1",
        enabled=True,
    )

    assert mapper.to_register_dict(result) == {
        "webhook": "github-ci",
        "status": "REGISTERED",
        "method": "POST",
        "auth": "signed",
        "payload_source": "body_json",
        "secret": "secret-1",
        "enabled": True,
    }


def test_mapper_serializes_list_and_remove_results() -> None:
    mapper = WebhookWaitMapper()

    list_result = ListWebhooksResult(
        webhooks=[
            WebhookRegistration(
                webhook="github-ci",
                secret="secret-1",
                method=WebhookMethod.POST,
                auth=WebhookAuth.SIGNED,
                payload_source=WebhookPayloadSource.BODY_JSON,
                enabled=True,
            )
        ]
    )
    remove_result = RemoveWebhookResult(
        status=RemoveWebhookStatus.REMOVED,
        webhook="github-ci",
    )

    assert mapper.to_list_dict(list_result) == [
        {
            "webhook": "github-ci",
            "secret": "secret-1",
            "method": "POST",
            "auth": "signed",
            "payload_source": "body_json",
            "token_header": None,
            "enabled": True,
            "created_at": None,
        }
    ]
    assert mapper.to_remove_input(" github-ci ") == "github-ci"
    assert mapper.to_remove_dict(remove_result) == {
        "webhook": "github-ci",
        "status": "REMOVED",
        "removed": True,
    }


def test_mapper_builds_token_authenticated_webhook_registration() -> None:
    mapper = WebhookWaitMapper()

    request = mapper.to_register_input(
        "telegram",
        method="POST",
        auth="token",
        payload_source="body_json",
        token_header=" X-Webhook-Token ",
    )

    assert request.auth == WebhookAuth.TOKEN
    assert request.token_header == "X-Webhook-Token"


def test_mapper_rejects_token_header_without_token_authentication() -> None:
    mapper = WebhookWaitMapper()

    with pytest.raises(ValueError, match="token authentication requires token_header"):
        mapper.to_register_input(
            "telegram",
            method="POST",
            auth="token",
            payload_source="body_json",
            token_header=None,
        )

    with pytest.raises(ValueError, match="only supported with token authentication"):
        mapper.to_register_input(
            "github",
            method="POST",
            auth="signed",
            payload_source="body_json",
            token_header="X-Webhook-Token",
        )


@pytest.mark.parametrize("token_header", ["Bad Header", "X:Token", "X-Ünicode"])
def test_mapper_rejects_invalid_http_token_header(token_header: str) -> None:
    mapper = WebhookWaitMapper()

    with pytest.raises(ValueError, match="valid HTTP field name"):
        mapper.to_register_input(
            "provider",
            method="POST",
            auth="token",
            payload_source="body_json",
            token_header=token_header,
        )
