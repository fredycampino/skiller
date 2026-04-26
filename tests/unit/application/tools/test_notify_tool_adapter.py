import pytest

from skiller.application.tools.notify import NotifyToolAdapter, NotifyToolRequest

pytestmark = pytest.mark.unit


def test_notify_tool_adapter_builds_request() -> None:
    adapter = NotifyToolAdapter()

    request = adapter.build_request(step_id="support_agent", value={"message": "ok"})

    assert request == NotifyToolRequest(message="ok")


def test_notify_tool_adapter_rejects_non_string_message() -> None:
    adapter = NotifyToolAdapter()

    with pytest.raises(ValueError, match="requires string message"):
        adapter.build_request(step_id="support_agent", value={})
