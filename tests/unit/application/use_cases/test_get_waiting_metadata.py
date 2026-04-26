from types import SimpleNamespace

import pytest

from skiller.application.use_cases.query.get_waiting_metadata import GetWaitingMetadataUseCase

pytestmark = pytest.mark.unit


def test_get_waiting_metadata_returns_webhook_data() -> None:
    run = SimpleNamespace(
        id="run-1",
        status="WAITING",
        current="wait_signal",
        skill_snapshot={
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
    skill_runner = SimpleNamespace(
        render_step=lambda step, context: {
            **step,
            "key": context["inputs"]["asset"],
        }
    )

    result = GetWaitingMetadataUseCase(store=store, skill_runner=skill_runner).execute("run-1")

    assert result == {
        "wait_type": "webhook",
        "webhook": "market-signal",
        "key": "btc-usd",
    }


def test_get_waiting_metadata_returns_input_prompt() -> None:
    run = SimpleNamespace(
        id="run-2",
        status="WAITING",
        current="ask_user",
        skill_snapshot={
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
    skill_runner = SimpleNamespace(render_step=lambda step, context: step)

    result = GetWaitingMetadataUseCase(store=store, skill_runner=skill_runner).execute("run-2")

    assert result == {
        "wait_type": "input",
        "prompt": "Write a short summary",
    }


def test_get_waiting_metadata_returns_channel_data() -> None:
    run = SimpleNamespace(
        id="run-3",
        status="WAITING",
        current="listen_whatsapp",
        skill_snapshot={
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
    skill_runner = SimpleNamespace(render_step=lambda step, context: step)

    result = GetWaitingMetadataUseCase(store=store, skill_runner=skill_runner).execute("run-3")

    assert result == {
        "wait_type": "channel",
        "channel": "whatsapp",
        "key": "all",
    }
