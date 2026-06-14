from pathlib import Path

import yaml


def test_flows_agent_uses_shell_and_files() -> None:
    agent_path = Path("packages/skiller/agents/flows/agent.yaml")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))

    agent_step = next(step for step in agent["steps"] if "agent" in step)

    assert agent_step["agent"] == "flows_agent"
    assert agent_step["system"] == {"file": "./system.md"}
    assert agent_step["tools"] == [
        "shell",
        "files",
    ]


def test_flows_system_owns_agentic_flow_guidance() -> None:
    system_path = Path("packages/skiller/agents/flows/system.md")
    system = system_path.read_text(encoding="utf-8")

    assert "You are Flows" in system
    assert "Agentic Flows `.yaml`" in system
    assert "flows/<group>/<name>.yaml" in system
    assert "../../docs/flows/flow-schema.md" in system
    assert "../../docs/steps/agent.md" in system
    assert "AGENT_DB_PATH" in system


def test_flows_onboarding_points_to_flows_agent() -> None:
    intro_path = Path("packages/skiller/agents/onboarding/intro.yaml")
    intro = intro_path.read_text(encoding="utf-8")

    assert "/run flows" in intro
    assert "skiller run flows" in intro
    assert "builder" not in intro
