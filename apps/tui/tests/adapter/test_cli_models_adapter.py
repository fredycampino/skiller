from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest

from stui.adapter.cli_models_adapter import CliModelsAdapter
from stui.port.models_port import ModelsPortModelItem, ModelsPortProviderItem

pytestmark = pytest.mark.unit


@dataclass
class FakeInvoker:
    completed: subprocess.CompletedProcess[str]
    called_with: tuple[str, ...] | None = None

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        self.called_with = args
        return self.completed


def test_cli_models_adapter_maps_runtime_payload() -> None:
    invoker = FakeInvoker(
        subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout=(
                '{"run_id":"run-1","status":"OK","ok":true,"providers":['
                '{"name":"codex","source":"global","models":['
                '{"name":"gpt-5.5","active":true}]}'
                ']}'
            ),
            stderr="",
        )
    )
    adapter = CliModelsAdapter(invoker=invoker)

    result = adapter.list_models(run_id="run-1")

    assert result == [
        ModelsPortProviderItem(
            name="codex",
            source="global",
            models=(ModelsPortModelItem(name="gpt-5.5", active=True),),
        )
    ]
    assert list(invoker.called_with or ()) == ["agent", "models", "run-1"]


def test_cli_models_adapter_selects_model() -> None:
    invoker = FakeInvoker(
        subprocess.CompletedProcess(
            args=["python", "-m", "skiller"],
            returncode=0,
            stdout=(
                '{"run_id":"run-1","provider":"minimax","model":"MiniMax-M2.5",'
                '"status":"OK","ok":true}'
            ),
            stderr="",
        )
    )
    adapter = CliModelsAdapter(invoker=invoker)

    adapter.select_model(
        run_id="run-1",
        provider="minimax",
        model="MiniMax-M2.5",
    )

    assert list(invoker.called_with or ()) == [
        "agent",
        "model",
        "run-1",
        "--provider",
        "minimax",
        "--model",
        "MiniMax-M2.5",
    ]


def test_cli_models_adapter_reports_runtime_failure() -> None:
    adapter = CliModelsAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
                args=["python", "-m", "skiller"],
                returncode=0,
                stdout='{"status":"RUN_NOT_FOUND","ok":false,"message":"run not found"}',
                stderr="",
            )
        )
    )

    with pytest.raises(RuntimeError, match="run not found"):
        adapter.list_models(run_id="missing")


def test_cli_models_adapter_reports_model_selection_failure() -> None:
    adapter = CliModelsAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
                args=["python", "-m", "skiller"],
                returncode=0,
                stdout='{"status":"MODEL_NOT_SUPPORTED","ok":false,"error":"bad model"}',
                stderr="",
            )
        )
    )

    with pytest.raises(RuntimeError, match="bad model"):
        adapter.select_model(
            run_id="run-1",
            provider="minimax",
            model="bad-model",
        )


def test_cli_models_adapter_rejects_invalid_payload() -> None:
    adapter = CliModelsAdapter(
        invoker=FakeInvoker(
            subprocess.CompletedProcess(
                args=["python", "-m", "skiller"],
                returncode=0,
                stdout="[]",
                stderr="",
            )
        )
    )

    with pytest.raises(RuntimeError, match="models command returned invalid payload"):
        adapter.list_models(run_id="run-1")
