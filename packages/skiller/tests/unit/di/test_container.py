import pytest

from skiller.di.container import build_runtime_container
from skiller.infrastructure.config.settings_model import Settings

pytestmark = pytest.mark.unit


def test_build_runtime_container_does_not_load_config_eagerly(tmp_path) -> None:
    settings = Settings(db_path=str(tmp_path / "runtime.db"))

    build_runtime_container(settings=settings, flows_dir=str(tmp_path))
