import pytest

from skiller.di.container import build_runtime_container
from skiller.infrastructure.config.settings_model import Settings

pytestmark = pytest.mark.unit


def test_build_runtime_container_does_not_load_config_eagerly(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    settings = Settings(db_path=str(tmp_path / "runtime.db"))

    build_runtime_container(settings=settings)


def test_build_runtime_container_initializes_config_before_opening_database(
    monkeypatch, tmp_path,
) -> None:
    import json

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("SKILLER_DB_PATH", raising=False)
    monkeypatch.delenv("SKILLER_RUNTIME_CONFIG_FILE", raising=False)

    container = build_runtime_container()

    settings_dir = tmp_path / "home/.skiller/settings"
    config = json.loads((settings_dir / "config.json").read_text())
    assert config["runtime"]["db_path"] == "~/.skiller/runtime/global.db"
    assert (settings_dir / "agent.flows.json").is_file()
    database = tmp_path / "home/.skiller/runtime/global.db"
    assert not database.exists()
    container.run_service.initialize()
    assert database.is_file()


def test_default_settings_initializes_database_in_home(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.db_path == str(home / ".skiller/runtime/global.db")
    container = build_runtime_container(settings=settings)
    container.run_service.initialize()
    assert (home / ".skiller/runtime/global.db").is_file()
    assert not (tmp_path / "~").exists()
