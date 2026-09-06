from pathlib import Path

import pytest

from skiller.infrastructure.flow.filesystem_packaged_flow_paths_port import (
    FilesystemPackagedFlowPathsPort,
)

pytestmark = pytest.mark.unit


def test_filesystem_packaged_flow_paths_port_returns_packaged_agents_directory() -> None:
    paths = FilesystemPackagedFlowPathsPort().get_paths()

    assert paths == (Path("apps/agents").resolve(),)
    assert paths[0].is_dir()
