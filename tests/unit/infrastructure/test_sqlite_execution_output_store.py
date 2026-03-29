import sqlite3

import pytest

from skiller.infrastructure.db.sqlite_execution_output_store import SqliteExecutionOutputStore

pytestmark = pytest.mark.unit


def test_init_db_creates_execution_outputs_table(tmp_path) -> None:
    db_path = tmp_path / "execution-outputs.db"
    store = SqliteExecutionOutputStore(str(db_path))

    store.init_db()

    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(execution_outputs)")]

    assert columns == [
        "id",
        "run_id",
        "step_id",
        "output_body_json",
        "created_at",
    ]


def test_store_and_get_execution_output_round_trip(tmp_path) -> None:
    db_path = tmp_path / "execution-output-round-trip.db"
    store = SqliteExecutionOutputStore(str(db_path))
    store.init_db()

    body_ref = store.store_execution_output(
        run_id="run-1",
        step_id="search",
        output_body={
            "total": 248,
            "items": [{"id": "a1"}, {"id": "a2"}],
        },
    )

    output_body = store.get_execution_output(body_ref)

    assert body_ref.startswith("execution_output:")
    assert output_body == {
        "total": 248,
        "items": [{"id": "a1"}, {"id": "a2"}],
    }


def test_get_execution_output_returns_none_for_unknown_ref(tmp_path) -> None:
    db_path = tmp_path / "execution-output-missing.db"
    store = SqliteExecutionOutputStore(str(db_path))
    store.init_db()

    output_body = store.get_execution_output("execution_output:missing")

    assert output_body is None


def test_get_execution_output_rejects_invalid_ref_prefix(tmp_path) -> None:
    db_path = tmp_path / "execution-output-invalid-ref.db"
    store = SqliteExecutionOutputStore(str(db_path))
    store.init_db()

    output_body = store.get_execution_output("output_ref:123")

    assert output_body is None
