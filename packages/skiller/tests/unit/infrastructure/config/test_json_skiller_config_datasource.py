import json
from pathlib import Path

import pytest

from skiller.domain.config.skiller_config import (
    RuntimeConfig,
    SkillerConfig,
    WebhooksConfig,
)
from skiller.infrastructure.config.json_skiller_config_datasource import (
    JsonSkillerConfigDatasource,
)
from skiller.infrastructure.config.skiller_config_mapper import SkillerConfigMapper

pytestmark = pytest.mark.unit


def test_json_skiller_config_datasource_reads_strict_config(tmp_path: Path) -> None:
    config_path = tmp_path / "settings" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "runtime": {
                    "db_path": "./runtime.db",
                    "log_level": "DEBUG",
                },
                "webhooks": {
                    "host": "0.0.0.0",
                    "port": 9002,
                },
                "flow_paths": ["./flows", "/opt/skiller/flows"],
            }
        ),
        encoding="utf-8",
    )

    config = _datasource().get_config(config_path)

    assert config == SkillerConfig(
        version=1,
        runtime=RuntimeConfig(
            db_path="./runtime.db",
            log_level="DEBUG",
        ),
        webhooks=WebhooksConfig(
            host="0.0.0.0",
            port=9002,
        ),
        flow_paths=(
            (config_path.parent / "flows").resolve(),
            Path("/opt/skiller/flows"),
        ),
    )


def test_json_skiller_config_datasource_uses_defaults_when_sections_are_missing(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")

    config = _datasource().get_config(config_path)

    assert config == SkillerConfig(
        version=1,
        runtime=RuntimeConfig(
            db_path="./runtime.db",
            log_level="INFO",
        ),
        webhooks=WebhooksConfig(
            host="127.0.0.1",
            port=8001,
        ),
        flow_paths=(),
    )


def test_json_skiller_config_datasource_returns_no_paths_when_paths_are_missing(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")

    config = _datasource().get_config(config_path)

    assert config.flow_paths == ()


def test_json_skiller_config_datasource_expands_home_in_flow_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home_path = tmp_path / "home"
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"flow_paths": ["~/flows"]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home_path))

    config = _datasource().get_config(config_path)

    assert config.flow_paths == ((home_path / "flows").resolve(),)


def test_json_skiller_config_datasource_resolves_runtime_cwd_template(
    tmp_path: Path,
) -> None:
    runtime_cwd = tmp_path / "workspace"
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"flow_paths": ["{{runtime.cwd}}/flows"]}',
        encoding="utf-8",
    )

    config = _datasource(runtime_cwd=runtime_cwd).get_config(config_path)

    assert config.flow_paths == ((runtime_cwd / "flows").resolve(),)


def test_json_skiller_config_datasource_rejects_unknown_flow_path_template(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"flow_paths": ["{{flow.dir}}/flows"]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported flow path template"):
        _datasource(runtime_cwd=tmp_path).get_config(config_path)


def test_json_skiller_config_datasource_rejects_unknown_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"unknown": true}', encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid Skiller config"):
        _datasource().get_config(config_path)


@pytest.mark.parametrize(
    "raw_config",
    ["[]", '"config"', "null"],
)
def test_json_skiller_config_datasource_rejects_non_object_root(
    tmp_path: Path,
    raw_config: str,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(raw_config, encoding="utf-8")

    with pytest.raises(ValueError, match="Skiller config must contain a JSON object"):
        _datasource().get_config(config_path)


@pytest.mark.parametrize(
    "paths",
    [
        [""],
        ["   "],
        [1],
        "./flows",
    ],
)
def test_json_skiller_config_datasource_rejects_invalid_flow_paths(
    tmp_path: Path,
    paths: object,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"flow_paths": paths}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid Skiller config"):
        _datasource().get_config(config_path)


def test_json_skiller_config_datasource_rejects_invalid_json(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"flow_paths":', encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid Skiller config JSON"):
        _datasource().get_config(config_path)


def test_json_skiller_config_datasource_uses_defaults_for_missing_file(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "missing.json"

    config = _datasource().get_config(config_path)

    assert config.runtime.db_path == "./runtime.db"
    assert config.webhooks.port == 8001
    assert config.flow_paths == ()


def test_json_skiller_config_datasource_reads_file_on_each_call(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"flow_paths": ["./first"]}',
        encoding="utf-8",
    )
    datasource = _datasource()

    first_config = datasource.get_config(config_path)
    config_path.write_text(
        '{"flow_paths": ["./second"]}',
        encoding="utf-8",
    )
    second_config = datasource.get_config(config_path)

    assert first_config.flow_paths == ((tmp_path / "first").resolve(),)
    assert second_config.flow_paths == ((tmp_path / "second").resolve(),)


def _datasource(
    runtime_cwd: Path = Path("/runtime/cwd"),
) -> JsonSkillerConfigDatasource:
    return JsonSkillerConfigDatasource(
        mapper=SkillerConfigMapper(runtime_cwd=runtime_cwd),
    )
