from pathlib import Path

import pytest

from skiller.application.config.service import RuntimeConfigApplicationService
from skiller.domain.config.skiller_config import RuntimeConfig, SkillerConfig, WebhooksConfig

pytestmark = pytest.mark.unit


class _FakeGetRuntimeConfigUseCase:
    def __init__(self, config: SkillerConfig) -> None:
        self.config = config
        self.calls = 0

    def execute(self) -> SkillerConfig:
        self.calls += 1
        return self.config


def test_runtime_config_service_returns_use_case_config() -> None:
    config = SkillerConfig(
        version=1,
        runtime=RuntimeConfig(db_path="runtime.db", log_level="INFO"),
        webhooks=WebhooksConfig(host="127.0.0.1", port=8001),
        flow_paths=(Path("flows"),),
    )
    get_runtime_config = _FakeGetRuntimeConfigUseCase(config)
    service = RuntimeConfigApplicationService(get_runtime_config)

    result = service.get_runtime_config()

    assert result == config
    assert get_runtime_config.calls == 1
