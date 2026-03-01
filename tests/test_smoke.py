from pathlib import Path
import tempfile

from runtime.application.runtime import Runtime
from runtime.infrastructure.db.sqlite_store import StateStore


def test_run_wait_and_resume_with_webhook() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store = StateStore(db_path)
        store.init_db()

        runtime = Runtime(store, skills_dir="skills")
        run_id = runtime.start_run(
            "create_release",
            {
                "repo": "demo",
                "base_branch": "main",
                "release_branch": "release/v1",
                "pr_title": "Release v1",
                "publish_target": "prod",
            },
        )

        run = store.get_run(run_id)
        assert run is not None
        assert run["status"] == "WAITING"

        resumed = runtime.handle_webhook(
            "webhook.merge.xyz",
            {"repo": "demo", "branch": "release/v1"},
        )
        assert run_id in resumed

        resumed_run = store.get_run(run_id)
        assert resumed_run is not None
        assert resumed_run["status"] == "SUCCEEDED"

        events = store.list_events(run_id)
        event_types = [event["type"] for event in events]
        assert "WAITING" in event_types
        assert "WAIT_RESOLVED" in event_types
        assert "RUN_FINISHED" in event_types
