from dataclasses import asdict

import pytest

from stui.adapter.events.cli_log_event import CliLogEvent
from stui.adapter.events.log_event_mapper import LogEventMapper
from stui.port.event_models import LogEventType
from stui.usecase.event_transcript_mapper import EventTranscriptMapper
from stui.usecase.project_agent_metrics_use_case import ProjectAgentMetricsUseCase
from stui.usecase.refresh_agent_metrics_use_case import RefreshAgentMetricsUseCase
from stui.viewmodel.console_screen_state import ConsoleScreenState

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "event_type",
    [
        LogEventType.AGENT_ASSISTANT_MESSAGE,
        LogEventType.AGENT_FINAL_ASSISTANT_MESSAGE,
        LogEventType.STEP_SUCCESS,
    ],
)
@pytest.mark.parametrize("metrics_case", ["absent", "valid", "zero_duration", "missing_duration"])
def test_generation_metrics_follow_usage_to_transcript_and_footer(event_type, metrics_case) -> None:
    with_metrics = metrics_case != "absent"
    usage = {
        "prompt_tokens": 20,
        "output_tokens": 5,
        "total_tokens": 25,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
        "provider": "ollama",
        "model": "qa-model",
    }
    metrics = {
        "total_duration_ns": 1000,
        "model_load_duration_ns": None,
        "input_tokens": 20,
        "input_processing_duration_ns": 200,
        "output_tokens": 5,
        "output_generation_duration_ns": 700,
    }
    if metrics_case == "zero_duration":
        metrics["output_generation_duration_ns"] = 0
    elif metrics_case == "missing_duration":
        metrics["output_generation_duration_ns"] = None
    data = {"usage": usage}
    if with_metrics:
        data["generation_metrics"] = metrics
    if event_type == LogEventType.STEP_SUCCESS:
        payload = {
            "output": {
                "text": "Done",
                "value": {
                    "data": {
                        **data,
                        "stop_reason": "final",
                        "final": "Done",
                        "context": None,
                    }
                },
            }
        }
    else:
        payload = {
            **data,
            "text": "" if event_type == LogEventType.AGENT_ASSISTANT_MESSAGE else "Done",
            "total_tokens": 25,
        }
    event = LogEventMapper().map(
        CliLogEvent.model_validate(
            {
                "sequence": 1,
                "id": "event-1",
                "run_id": "run-1",
                "type": event_type,
                "step_id": "qa",
                "step_type": "agent",
                "created_at": "2026-01-01T00:00:00Z",
                "payload": payload,
            }
        )
    )
    items = EventTranscriptMapper().to_transcript([event])
    assert len(items) == 1
    item = items[0]
    assert item.usage.output_tokens == 5
    assert (asdict(item.generation_metrics) if item.generation_metrics else None) == (
        metrics if with_metrics else None
    )
    if event_type == LogEventType.AGENT_ASSISTANT_MESSAGE:
        assert item.text == "▪▪▪"
        assert item.is_empty
    if event_type == LogEventType.AGENT_FINAL_ASSISTANT_MESSAGE:
        # Final message projection remains unchanged: the footer uses STEP_SUCCESS.
        assert item.text == "Done"
        return
    expected_speed = 5 * 1e9 / 700 if metrics_case == "valid" else None
    assert item.output_tokens_per_second == expected_speed
    projected = ProjectAgentMetricsUseCase().execute(items=items)
    state = (
        RefreshAgentMetricsUseCase()
        .execute(
            state=ConsoleScreenState(),
            metrics=projected,
        )
        .state
    )
    assert state.agent_metrics.usage == item.usage
    assert state.agent_metrics.generation_metrics == item.generation_metrics
