import pytest

from skiller.domain.flow.flow_raw_definition import RawAction
from skiller.infrastructure.flow.flow_yaml_mapper import FlowYamlMapper

pytestmark = pytest.mark.unit


def test_flow_yaml_mapper_maps_raw_flow_definition() -> None:
    flow = FlowYamlMapper().to_flow(
        {
            "name": "demo",
            "start": "intro",
            "steps": [
                {
                    "notify": "intro",
                    "message": "Hello",
                    "next": "done",
                }
            ],
            "on_success": {
                "action": {
                    "type": "run",
                    "label": "Run next",
                    "arg": "--file next.yaml",
                }
            },
        }
    )

    assert flow.name == "demo"
    assert flow.start == "intro"
    assert flow.raw is not None
    assert flow.on_success is not None
    assert flow.on_success.trigger == "on_success"
    assert flow.on_success.action == RawAction(
        type="run",
        label="Run next",
        arg="--file next.yaml",
        raw={
            "type": "run",
            "label": "Run next",
            "arg": "--file next.yaml",
        },
    )
    assert flow.on_error is None
    assert len(flow.steps) == 1
    assert flow.steps[0].index == 0
    assert flow.steps[0].step_id == "intro"
    assert flow.steps[0].step_type == "notify"
    assert flow.steps[0].body == {
        "message": "Hello",
        "next": "done",
    }


def test_flow_yaml_mapper_preserves_unknown_step_type_for_validation() -> None:
    flow = FlowYamlMapper().to_flow(
        {
            "name": "demo",
            "start": "intro",
            "steps": [
                {
                    "unknown": "intro",
                    "message": "Hello",
                }
            ],
        }
    )

    assert flow.steps[0].step_type == "unknown"
    assert flow.steps[0].step_id == "intro"
    assert flow.steps[0].body == {"message": "Hello"}


def test_flow_yaml_mapper_maps_empty_step_for_validation() -> None:
    flow = FlowYamlMapper().to_flow(
        {
            "name": "demo",
            "start": "intro",
            "steps": [{}],
        }
    )

    assert flow.steps[0].step_type is None
    assert flow.steps[0].step_id is None
    assert flow.steps[0].body == {}


def test_flow_yaml_mapper_keeps_missing_flow_fields_as_none() -> None:
    flow = FlowYamlMapper().to_flow({"steps": []})

    assert flow.name is None
    assert flow.start is None
    assert flow.steps == ()


def test_flow_yaml_mapper_keeps_invalid_action_fields_as_none_or_raw() -> None:
    flow = FlowYamlMapper().to_flow(
        {
            "steps": [],
            "on_error": {
                "action": {
                    "type": "run",
                    "label": 123,
                    "arg": "--file fallback.yaml",
                    "auto": "yes",
                }
            },
        }
    )

    assert flow.on_error is not None
    assert flow.on_error.action == RawAction(
        type="run",
        label=None,
        arg="--file fallback.yaml",
        auto="yes",
        raw={
            "type": "run",
            "label": 123,
            "arg": "--file fallback.yaml",
            "auto": "yes",
        },
    )


def test_flow_yaml_mapper_maps_non_object_flow_for_validation() -> None:
    flow = FlowYamlMapper().to_flow([])

    assert flow.name is None
    assert flow.start is None
    assert flow.steps is None
    assert flow.raw == []


def test_flow_yaml_mapper_maps_non_list_steps_for_validation() -> None:
    flow = FlowYamlMapper().to_flow({"name": "demo", "start": "intro", "steps": {}})

    assert flow.steps is None
    assert flow.raw == {"name": "demo", "start": "intro", "steps": {}}
