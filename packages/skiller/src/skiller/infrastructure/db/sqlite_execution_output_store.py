import json
import uuid
from pathlib import Path
from typing import Any

from skiller.infrastructure.db.sqlite_repository import SqliteRepository

_BODY_REF_PREFIX = "execution_output:"


class SqliteExecutionOutputStore(SqliteRepository):
    def init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS execution_outputs (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  step_id TEXT NOT NULL,
                  output_body_json TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_execution_outputs_run_step_created_at
                  ON execution_outputs(run_id, step_id, created_at);
                """
            )

    def store_execution_output(
        self,
        *,
        run_id: str,
        step_id: str,
        output_body: dict[str, Any],
    ) -> str:
        output_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO execution_outputs (
                  id,
                  run_id,
                  step_id,
                  output_body_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    output_id,
                    run_id,
                    step_id,
                    json.dumps(output_body),
                ),
            )
        return f"{_BODY_REF_PREFIX}{output_id}"

    def get_execution_output(self, body_ref: str) -> dict[str, Any] | None:
        output_id = self._extract_output_id(body_ref)
        if output_id is None:
            return None

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT output_body_json
                FROM execution_outputs
                WHERE id = ?
                """,
                (output_id,),
            ).fetchone()
        if row is None:
            return None

        raw_output_body = row["output_body_json"]
        if not isinstance(raw_output_body, str) or not raw_output_body.strip():
            return None

        output_body = json.loads(raw_output_body)
        return output_body if isinstance(output_body, dict) else None

    def _extract_output_id(self, body_ref: str) -> str | None:
        normalized = body_ref.strip()
        if not normalized.startswith(_BODY_REF_PREFIX):
            return None

        output_id = normalized.removeprefix(_BODY_REF_PREFIX).strip()
        return output_id or None
