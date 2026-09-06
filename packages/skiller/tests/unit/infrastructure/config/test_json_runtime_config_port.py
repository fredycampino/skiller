import json
from pathlib import Path

import pytest

from skiller.infrastructure.config.json_runtime_config_port import JsonRuntimeConfigPort
from skiller.infrastructure.config.json_skiller_config_datasource import (
    JsonSkillerConfigDatasource,
)
from skiller.infrastructure.config.skiller_config_mapper import SkillerConfigMapper

pytestmark = pytest.mark.unit


def test_json_runtime_config_port_returns_mapped_paths_in_order(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "settings" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "flow_paths": ["./flows", "/opt/skiller/flows"],
            }
        ),
        encoding="utf-8",
    )
    port = JsonRuntimeConfigPort(
        config_datasource=JsonSkillerConfigDatasource(
            mapper=SkillerConfigMapper(runtime_cwd=tmp_path),
        ),
    )

    config = port.get_config(config_path)

    assert config.flow_paths == (
        (config_path.parent / "flows").resolve(),
        Path("/opt/skiller/flows"),
    )


def test_json_runtime_config_port_returns_empty_paths_when_not_configured(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    port = JsonRuntimeConfigPort(
        config_datasource=JsonSkillerConfigDatasource(
            mapper=SkillerConfigMapper(runtime_cwd=tmp_path),
        ),
    )

    config = port.get_config(config_path)

    assert config.flow_paths == ()
