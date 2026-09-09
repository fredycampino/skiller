from pathlib import Path

import pytest

from skiller.application.use_cases.config.get_runtime_config import (
    GetRuntimeConfigUseCase,
)
from skiller.domain.config.skiller_config import (
    RuntimeConfig,
    SkillerConfig,
    WebhooksConfig,
)

pytestmark = pytest.mark.unit


class _FakeRuntimeConfigPort:
    def __init__(self, configs: dict[Path, SkillerConfig]) -> None:
        self.configs = configs
        self.config_paths: list[Path] = []

    def get_config(self, config_path: Path) -> SkillerConfig:
        self.config_paths.append(config_path)
        return self.configs[config_path]


class _FakePackagedFlowPathsPort:
    def __init__(self, paths: tuple[Path, ...] = ()) -> None:
        self.paths = paths

    def get_paths(self) -> tuple[Path, ...]:
        return self.paths


def test_get_runtime_config_uses_environment_path(tmp_path: Path) -> None:
    environment_path = tmp_path / "environment.json"
    environment_path.write_text("{}", encoding="utf-8")
    default_path = tmp_path / "default.json"
    environment_config = _config(Path("/flows/environment"))
    runtime_config = _FakeRuntimeConfigPort(configs={environment_path: environment_config})
    use_case = GetRuntimeConfigUseCase(
        runtime_config=runtime_config,
        packaged_flow_paths=_FakePackagedFlowPathsPort(),
        environment_config_path=str(environment_path),
        default_config_path=default_path,
        runtime_cwd=Path("/flows/environment"),
    )

    result = use_case.execute()

    assert result == environment_config
    assert runtime_config.config_paths == [environment_path]


@pytest.mark.parametrize("environment_config_path", [None, "", "   "])
def test_get_runtime_config_uses_default_path_when_environment_path_is_empty(
    environment_config_path: str | None,
) -> None:
    default_path = Path("/settings/default.json")
    default_config = _config(Path("/flows/default"))
    runtime_config = _FakeRuntimeConfigPort(configs={default_path: default_config})
    use_case = GetRuntimeConfigUseCase(
        runtime_config=runtime_config,
        packaged_flow_paths=_FakePackagedFlowPathsPort(),
        environment_config_path=environment_config_path,
        default_config_path=default_path,
        runtime_cwd=Path("/flows/default"),
    )

    result = use_case.execute()

    assert result == default_config
    assert runtime_config.config_paths == [default_path]


def test_get_runtime_config_strips_environment_path(tmp_path: Path) -> None:
    environment_path = tmp_path / "environment.json"
    environment_path.write_text("{}", encoding="utf-8")
    environment_config = _config(Path("/flows/environment"))
    runtime_config = _FakeRuntimeConfigPort(configs={environment_path: environment_config})
    use_case = GetRuntimeConfigUseCase(
        runtime_config=runtime_config,
        packaged_flow_paths=_FakePackagedFlowPathsPort(),
        environment_config_path=f"  {environment_path}  ",
        default_config_path=tmp_path / "default.json",
        runtime_cwd=Path("/flows/environment"),
    )

    result = use_case.execute()

    assert result == environment_config
    assert runtime_config.config_paths == [environment_path]


def test_get_runtime_config_rejects_missing_environment_path(tmp_path: Path) -> None:
    environment_path = tmp_path / "missing.json"
    runtime_config = _FakeRuntimeConfigPort(configs={})
    use_case = GetRuntimeConfigUseCase(
        runtime_config=runtime_config,
        packaged_flow_paths=_FakePackagedFlowPathsPort(),
        environment_config_path=str(environment_path),
        default_config_path=tmp_path / "default.json",
        runtime_cwd=tmp_path,
    )

    with pytest.raises(FileNotFoundError, match="Missing Skiller config"):
        use_case.execute()

    assert runtime_config.config_paths == []


def test_get_runtime_config_adds_flow_paths_without_duplicates() -> None:
    default_path = Path("/settings/default.json")
    configured_path = Path("/flows/configured")
    packaged_path = Path("/apps/agents")
    runtime_config = _FakeRuntimeConfigPort(
        configs={default_path: _config(configured_path)},
    )
    use_case = GetRuntimeConfigUseCase(
        runtime_config=runtime_config,
        packaged_flow_paths=_FakePackagedFlowPathsPort(
            (packaged_path, configured_path,)
        ),
        environment_config_path=None,
        default_config_path=default_path,
        runtime_cwd=configured_path,
    )

    result = use_case.execute()

    assert result.flow_paths == (packaged_path, configured_path)


def test_get_runtime_config_orders_packaged_cwd_and_configured_flow_paths(
    tmp_path: Path,
) -> None:
    default_path = tmp_path / "settings" / "default.json"
    configured_path = tmp_path / "configured"
    runtime_cwd = tmp_path / "workspace"
    packaged_path = tmp_path / "packaged"
    runtime_config = _FakeRuntimeConfigPort(
        configs={default_path: _config(configured_path)},
    )
    use_case = GetRuntimeConfigUseCase(
        runtime_config=runtime_config,
        packaged_flow_paths=_FakePackagedFlowPathsPort(
            (packaged_path, runtime_cwd, configured_path)
        ),
        environment_config_path=None,
        default_config_path=default_path,
        runtime_cwd=runtime_cwd,
    )

    result = use_case.execute()

    assert result.flow_paths == (
        packaged_path,
        runtime_cwd.resolve(),
        configured_path,
    )


def _config(flow_path: Path) -> SkillerConfig:
    return SkillerConfig(
        version=1,
        runtime=RuntimeConfig(
            db_path="./runtime.db",
            log_level="INFO",
        ),
        webhooks=WebhooksConfig(
            host="127.0.0.1",
            port=8001,
        ),
        flow_paths=(flow_path,),
    )
