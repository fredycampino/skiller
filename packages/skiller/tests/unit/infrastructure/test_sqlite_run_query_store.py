import pytest

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import RunStatus
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType
from skiller.domain.wait.wait_type import WaitType
from skiller.infrastructure.db.datasource.sqlite_wait_datasource import SqliteWaitDatasource
from skiller.infrastructure.db.sqlite_run_query_store import SqliteRunQueryStore
from skiller.infrastructure.db.sqlite_run_store_port import SqliteRunStorePort
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap
from skiller.infrastructure.db.sqlite_wait_store_port import SqliteWaitStorePort

pytestmark = pytest.mark.unit


def test_list_runs_returns_recent_runs_first(tmp_path) -> None:
    db_path = tmp_path / "runs.db"
    run_store = SqliteRunStorePort(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    query_store = SqliteRunQueryStore(str(db_path))

    first_run_id = "550e8400-e29b-41d4-a716-446655440010"
    second_run_id = "550e8400-e29b-41d4-a716-446655440011"

    run_store.create_run(
        "internal",
        "notify_test",
        {"start": "show_message", "steps": [{"notify": "show_message"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=first_run_id,
    )
    run_store.create_run(
        "internal",
        "wait_input_test",
        {"start": "ask_user", "steps": [{"wait_input": "ask_user"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=second_run_id,
    )
    run_store.update_run(first_run_id, status=RunStatus.SUCCEEDED)
    run_store.update_run(second_run_id, status=RunStatus.WAITING)

    runs = query_store.list_runs(limit=20)

    assert [run.id for run in runs] == [second_run_id, first_run_id]
    assert runs[0].ref == "wait_input_test"
    assert runs[1].ref == "notify_test"
    assert runs[0].wait_type is None


def test_list_runs_can_filter_by_status(tmp_path) -> None:
    db_path = tmp_path / "runs-filter.db"
    run_store = SqliteRunStorePort(str(db_path))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    query_store = SqliteRunQueryStore(str(db_path))

    waiting_run_id = "550e8400-e29b-41d4-a716-446655440012"
    failed_run_id = "550e8400-e29b-41d4-a716-446655440013"

    run_store.create_run(
        "internal",
        "wait_input_test",
        {"start": "ask_user", "steps": [{"wait_input": "ask_user"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=waiting_run_id,
    )
    run_store.create_run(
        "internal",
        "pull_request",
        {"start": "call_tool", "steps": [{"mcp": "call_tool", "server": "github"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=failed_run_id,
    )
    run_store.update_run(waiting_run_id, status=RunStatus.WAITING)
    run_store.update_run(failed_run_id, status=RunStatus.FAILED)

    runs = query_store.list_runs(limit=20, statuses=["waiting"])

    assert [run.id for run in runs] == [waiting_run_id]
    assert runs[0].status == RunStatus.WAITING.value


def test_list_runs_includes_wait_type_and_webhook_detail(tmp_path) -> None:
    db_path = tmp_path / "runs-waits.db"
    run_store = SqliteRunStorePort(str(db_path))
    wait_store = SqliteWaitStorePort(SqliteWaitDatasource(str(db_path)))
    SqliteRuntimeBootstrap(str(db_path)).init_db()
    query_store = SqliteRunQueryStore(str(db_path))

    webhook_run_id = "550e8400-e29b-41d4-a716-446655440014"
    input_run_id = "550e8400-e29b-41d4-a716-446655440015"

    run_store.create_run(
        "internal",
        "webhook_signal_oracle",
        {"start": "wait_signal", "steps": [{"wait_webhook": "wait_signal"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=webhook_run_id,
    )
    run_store.create_run(
        "internal",
        "chat",
        {"start": "ask_user", "steps": [{"wait_input": "ask_user"}]},
        RunContext(inputs={}, step_executions={}),
        run_id=input_run_id,
    )
    wait_store.create_wait(
        webhook_run_id,
        step_id="wait_signal",
        wait_type=WaitType.WEBHOOK,
        source_type=SourceType.WEBHOOK,
        source_name="github-ci",
        match_type=MatchType.SIGNAL,
        match_key="42",
    )
    wait_store.create_wait(
        input_run_id,
        step_id="ask_user",
        wait_type=WaitType.INPUT,
        source_type=SourceType.INPUT,
        source_name="manual",
        match_type=MatchType.RUN,
        match_key=input_run_id,
    )
    run_store.update_run(webhook_run_id, status=RunStatus.WAITING, current="wait_signal")
    run_store.update_run(input_run_id, status=RunStatus.WAITING, current="ask_user")

    runs = query_store.list_runs(limit=20, statuses=["waiting"])

    assert [run.id for run in runs] == [input_run_id, webhook_run_id]
    assert runs[0].wait_type == "input"
    assert runs[0].wait_detail is None
    assert runs[1].wait_type == "webhook"
    assert runs[1].wait_detail == "github-ci:42"
