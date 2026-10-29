import json
import os
from pathlib import Path

import pytest

from skiller.infrastructure.config.json_runtime_config_initializer import _write_atomic


@pytest.mark.parametrize("replace", [False, True])
def test_published_config_is_complete(monkeypatch, tmp_path, replace):
    destination = tmp_path / "config.json"
    previous = '{"custom": true}'
    if replace:
        destination.write_text(previous)
    publish = os.replace if replace else os.link

    def inspect_publish(source, target):
        assert json.loads(Path(source).read_text()) == {"runtime": {"db_path": "global.db"}}
        if replace:
            assert destination.read_text() == previous
        else:
            assert not destination.exists()
        publish(source, target)

    monkeypatch.setattr(os, "replace" if replace else "link", inspect_publish)
    _write_atomic(destination, '{"runtime": {"db_path": "global.db"}}', replace=replace)
    assert json.loads(destination.read_text())["runtime"]["db_path"] == "global.db"
    assert list(tmp_path.iterdir()) == [destination]


def test_concurrent_profile_creation_preserves_winner(monkeypatch, tmp_path):
    destination = tmp_path / "agent.flows.json"
    link = os.link

    def create_other_profile(source, target):
        destination.write_text('{"custom": true}')
        link(source, target)

    monkeypatch.setattr(os, "link", create_other_profile)
    _write_atomic(destination, '{"default": true}', replace=False)
    assert json.loads(destination.read_text()) == {"custom": True}
    assert list(tmp_path.iterdir()) == [destination]


def test_failed_publication_preserves_config_and_removes_temporary(monkeypatch, tmp_path):
    destination = tmp_path / "config.json"
    destination.write_text('{"custom": true}')

    def fail_publish(source, target):
        raise OSError("publication failed")

    monkeypatch.setattr(os, "replace", fail_publish)
    with pytest.raises(OSError, match="publication failed"):
        _write_atomic(destination, '{"default": true}', replace=True)
    assert json.loads(destination.read_text()) == {"custom": True}
    assert list(tmp_path.iterdir()) == [destination]
