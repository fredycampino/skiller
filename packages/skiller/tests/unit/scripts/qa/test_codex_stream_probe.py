from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[6]))

from scripts.qa.codex.codex_stream_probe import (
    CodexProbeIdentity,
    CodexProbeRunner,
    CodexProbeStreamResult,
    CodexProbeTraceWriter,
    CodexProbeVariant,
    _function_arguments_metadata,
    build_continuation_request,
    build_seed_request,
    load_probe_source,
)


def test_load_probe_source_reconstructs_request_before_final_tool_batch(tmp_path: Path) -> None:
    source = load_probe_source(_write_source(tmp_path))

    assert source.sequence == 2
    assert source.seed_input == ({"role": "user", "content": "use shell"},)
    assert source.recorded_tool_outputs[0].name == "shell"
    assert source.recorded_tool_outputs[0].output == "recorded output"


def test_baseline_continuation_omits_hidden_state_and_reasoning(tmp_path: Path) -> None:
    source = load_probe_source(_write_source(tmp_path))
    identity = _identity(source)
    seed_request = build_seed_request(
        source,
        variant=CodexProbeVariant.BASELINE,
        identity=identity,
    )
    continuation = build_continuation_request(
        source,
        seed_request=seed_request,
        seed_result=_seed_result(),
        variant=CodexProbeVariant.BASELINE,
        identity=identity,
    )

    assert continuation is not None
    assert "reasoning" not in continuation
    assert "x-codex-turn-state" not in continuation["extra_headers"]


def test_combined_continuation_replays_turn_state_and_reasoning(tmp_path: Path) -> None:
    source = load_probe_source(_write_source(tmp_path))
    identity = _identity(source)
    seed_request = build_seed_request(
        source,
        variant=CodexProbeVariant.COMBINED,
        identity=identity,
    )
    continuation = build_continuation_request(
        source,
        seed_request=seed_request,
        seed_result=_seed_result(),
        variant=CodexProbeVariant.COMBINED,
        identity=identity,
    )

    assert continuation is not None
    assert continuation["reasoning"] == {"effort": "medium"}
    assert continuation["extra_headers"]["x-codex-turn-state"] == "opaque-turn-state"


def test_lite_variant_uses_lite_framing_and_preserves_output_items(tmp_path: Path) -> None:
    source = load_probe_source(_write_source(tmp_path))
    identity = _identity(source)
    seed_request = build_seed_request(
        source,
        variant=CodexProbeVariant.LITE,
        identity=identity,
    )
    continuation = build_continuation_request(
        source,
        seed_request=seed_request,
        seed_result=_seed_result(),
        variant=CodexProbeVariant.LITE,
        identity=identity,
    )

    assert seed_request["parallel_tool_calls"] is False
    assert seed_request["reasoning"] == {"effort": "medium", "context": "all_turns"}
    assert continuation is not None
    assert continuation["extra_headers"]["x-openai-internal-codex-responses-lite"] == "true"
    assert any(item.get("type") == "reasoning" for item in continuation["input"])


def test_runner_trace_does_not_persist_prompt_or_opaque_state(tmp_path: Path) -> None:
    source = load_probe_source(_write_source(tmp_path))
    trace_path = tmp_path / "trace.jsonl"
    writer = CodexProbeTraceWriter(trace_path)
    runner = CodexProbeRunner(
        stream_client=_FakeStreamClient([_seed_result(), _continuation_result()]),
        trace_writer=writer,
    )

    runner.run(source, variant=CodexProbeVariant.LITE, identity=_identity(source))

    trace = trace_path.read_text(encoding="utf-8")
    assert "system secret" not in trace
    assert "use shell" not in trace
    assert "recorded output" not in trace
    assert "opaque-turn-state" not in trace


def test_runner_sends_seed_and_one_continuation(tmp_path: Path) -> None:
    source = load_probe_source(_write_source(tmp_path))
    client = _FakeStreamClient([_seed_result(), _continuation_result()])
    runner = CodexProbeRunner(
        stream_client=client,
        trace_writer=CodexProbeTraceWriter(tmp_path / "trace.jsonl"),
    )

    seed_result, continuation_result = runner.run(
        source,
        variant=CodexProbeVariant.TURN_STATE,
        identity=_identity(source),
    )

    assert seed_result.completed is True
    assert continuation_result is not None
    assert len(client.requests) == 2


def test_function_argument_metadata_contains_no_argument_content() -> None:
    metadata = _function_arguments_metadata('{"command":"secret"}', delta_events=2)

    assert metadata["utf8_bytes"] > 0
    assert metadata["sha256_prefix"]
    assert "secret" not in json.dumps(metadata)


class _FakeStreamClient:
    def __init__(self, results: list[CodexProbeStreamResult]) -> None:
        self.results = iter(results)
        self.requests: list[tuple[dict[str, object], str]] = []

    def stream(
        self,
        request: dict[str, object],
        *,
        phase: str,
    ) -> CodexProbeStreamResult:
        self.requests.append((request, phase))
        return next(self.results)


def _identity(source) -> CodexProbeIdentity:
    return CodexProbeIdentity.from_source(source)


def _seed_result() -> CodexProbeStreamResult:
    return CodexProbeStreamResult(
        completed=True,
        terminal_event="response.completed",
        turn_state="opaque-turn-state",
        output_items=(
            {
                "type": "reasoning",
                "id": "reasoning-1",
                "summary": [],
                "encrypted_content": "secret-reasoning",
            },
            {
                "type": "function_call",
                "call_id": "call-1",
                "name": "shell",
                "arguments": '{"command":"pwd"}',
            },
        ),
        output_text="",
        event_count=4,
        serialized_event_bytes=100,
        error=None,
    )


def _continuation_result() -> CodexProbeStreamResult:
    return CodexProbeStreamResult(
        completed=True,
        terminal_event="response.completed",
        turn_state="opaque-turn-state",
        output_items=(),
        output_text="done",
        event_count=2,
        serialized_event_bytes=20,
        error=None,
    )


def _write_source(tmp_path: Path) -> Path:
    source_path = tmp_path / "request.json"
    payload = {
        "sequence": 2,
        "request": {
            "model": "gpt-5.6-luna",
            "instructions": "system secret",
            "input": [
                {"role": "user", "content": "use shell"},
                {
                    "type": "function_call",
                    "call_id": "old-call",
                    "name": "shell",
                    "arguments": '{"command":"old"}',
                },
                {
                    "type": "function_call_output",
                    "call_id": "old-call",
                    "output": "recorded output",
                },
            ],
            "tools": [
                {
                    "type": "function",
                    "name": "shell",
                    "description": "run a command",
                    "parameters": {"type": "object"},
                }
            ],
            "parallel_tool_calls": True,
        },
    }
    source_path.write_text(json.dumps(payload), encoding="utf-8")
    return source_path
