from types import SimpleNamespace

import pytest

from skiller.application.use_cases.query.get_waiting_metadata import GetWaitingMetadataUseCase

pytestmark = pytest.mark.unit


class _FakeSkillRunner:
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


def test_get_waiting_metadata_returns_webhook_data() -> None:
    run = SimpleNamespace(
        id="run-1",
        source="internal",
        ref="demo",
        status="WAITING",
        current="wait_signal",
        snapshot={
            "steps": [
                {
                    "wait_webhook": "wait_signal",
                    "webhook": "market-signal",
                    "key": "{{inputs.asset}}",
                }
            ]
        },
        context=SimpleNamespace(to_dict=lambda: {"inputs": {"asset": "btc-usd"}, "results": {}}),
    )

    store = SimpleNamespace(get_run=lambda run_id: run if run_id == "run-1" else None)
    skill_runner = _FakeSkillRunner()

    result = GetWaitingMetadataUseCase(store=store, skill_runner=skill_runner).execute("run-1")

    assert result == {
        "wait_type": "webhook",
        "webhook": "market-signal",
        "key": "btc-usd",
    }
    assert skill_runner.render_calls[0]["flow"] is run


def test_get_waiting_metadata_returns_input_prompt() -> None:
    run = SimpleNamespace(
        id="run-2",
        source="internal",
        ref="demo",
        status="WAITING",
        current="ask_user",
        snapshot={
            "steps": [
                {
                    "wait_input": "ask_user",
                    "prompt": "Write a short summary",
                }
            ]
        },
        context=SimpleNamespace(to_dict=lambda: {"inputs": {}, "results": {}}),
    )

    store = SimpleNamespace(get_run=lambda run_id: run if run_id == "run-2" else None)
    skill_runner = _FakeSkillRunner()

    result = GetWaitingMetadataUseCase(store=store, skill_runner=skill_runner).execute("run-2")

    assert result == {
        "wait_type": "input",
        "prompt": "Write a short summary",
    }
    assert skill_runner.render_calls[0]["flow"] is run


def test_get_waiting_metadata_returns_channel_data() -> None:
    run = SimpleNamespace(
        id="run-3",
        source="internal",
        ref="demo",
        status="WAITING",
        current="listen_whatsapp",
        snapshot={
            "steps": [
                {
                    "wait_channel": "listen_whatsapp",
                    "channel": "whatsapp",
                    "key": "all",
                }
            ]
        },
        context=SimpleNamespace(to_dict=lambda: {"inputs": {}, "results": {}}),
    )

    store = SimpleNamespace(get_run=lambda run_id: run if run_id == "run-3" else None)
    skill_runner = _FakeSkillRunner()

    result = GetWaitingMetadataUseCase(store=store, skill_runner=skill_runner).execute("run-3")

    assert result == {
        "wait_type": "channel",
        "channel": "whatsapp",
        "key": "all",
    }
    assert skill_runner.render_calls[0]["flow"] is run
