import json
from pathlib import Path

import pytest

from skiller.application.runs.models import RunRequest
from skiller.application.use_cases.flow.resolve_flow import (
    ResolveFlowInput,
    ResolveFlowStatus,
    ResolveFlowUseCase,
)
from skiller.di.container import build_runtime_container
from skiller.domain.flow.flow_reference import FlowReference
from skiller.infrastructure.config.settings_model import Settings

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "reference",
    [
        "@flows",
        "@pr",
        "@info/info",
        "@auths/auth",
        "@auths/bedrock",
        "@auths/codex",
        "@auths/lmstudio",
        "@auths/minimax",
        "@auths/moonshot",
        "@auths/openai",
    ],
)
def test_packaged_flow_references_resolve(reference: str, tmp_path: Path) -> None:
    result = ResolveFlowUseCase(home_path=tmp_path).execute(
        ResolveFlowInput(
            reference=FlowReference(reference),
            flow_paths=(Path("apps/agents").resolve(),),
        )
    )

    assert result.status is ResolveFlowStatus.RESOLVED


def test_runtime_reloads_configured_flow_paths_for_each_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.json"
    database_path = tmp_path / "runtime.db"
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _write_flow(first_root / "reports" / "daily.yaml", name="daily")
    _write_flow(second_root / "reports" / "monthly.yaml", name="monthly")
    _write_config(config_path, database_path=database_path, flow_path=first_root)
    monkeypatch.setenv("AGENT_RUNTIME_CONFIG_FILE", str(config_path))

    settings = Settings(db_path=str(database_path))
    container = build_runtime_container(settings=settings)
    container.run_service.initialize()

    first = container.run_service.create_run(
        RunRequest(reference=FlowReference("@reports/daily"), inputs={})
    )
    first_run = container.run_service.get_run_use_case.execute(first.run_id)

    _write_config(config_path, database_path=database_path, flow_path=second_root)
    second = container.run_service.create_run(
        RunRequest(reference=FlowReference("@reports/monthly"), inputs={})
    )
    second_run = container.run_service.get_run_use_case.execute(second.run_id)

    assert database_path.is_file()
    assert first_run is not None
    assert first_run.flow_path == (first_root / "reports" / "daily.yaml").resolve()
    assert second_run is not None
    assert second_run.flow_path == (second_root / "reports" / "monthly.yaml").resolve()


def _write_config(config_path: Path, *, database_path: Path, flow_path: Path) -> None:
    config_path.write_text(
        json.dumps(
            {
                "runtime": {"db_path": str(database_path)},
                "flow_paths": [str(flow_path)],
            }
        ),
        encoding="utf-8",
    )


def _write_flow(flow_path: Path, *, name: str) -> None:
    flow_path.parent.mkdir(parents=True)
    flow_path.write_text(
        f"name: {name}\nstart: done\nsteps:\n  - notify: done\n    message: ok\n",
        encoding="utf-8",
    )
