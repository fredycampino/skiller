from __future__ import annotations

import json

import pytest

from stui.adapter.file_session_store_adapter import FileSessionStoreAdapter
from stui.port.session_store_port import StoredSession

pytestmark = pytest.mark.unit


def test_file_session_store_adapter_writes_and_reads_session(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "session.json"
    adapter = FileSessionStoreAdapter(path=path)

    adapter.write(StoredSession(run_id=" run-1 ", run_name=" chat "))

    assert adapter.read() == StoredSession(run_id="run-1", run_name="chat")
    assert json.loads(path.read_text()) == {"run_id": "run-1", "run_name": "chat"}


def test_file_session_store_adapter_returns_none_for_missing_or_invalid_file(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "session.json"
    adapter = FileSessionStoreAdapter(path=path)

    assert adapter.read() is None

    path.write_text("{")

    assert adapter.read() is None


def test_file_session_store_adapter_clears_session(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "session.json"
    adapter = FileSessionStoreAdapter(path=path)
    adapter.write(StoredSession(run_id="run-1", run_name="chat"))

    adapter.clear()

    assert adapter.read() is None
    assert not path.exists()


def test_file_session_store_adapter_empty_write_clears_session(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "session.json"
    adapter = FileSessionStoreAdapter(path=path)
    adapter.write(StoredSession(run_id="run-1", run_name="chat"))

    adapter.write(StoredSession(run_id=" ", run_name="chat"))

    assert adapter.read() is None
