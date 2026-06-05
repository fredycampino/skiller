import json

from skiller.domain.run.run_model import RunAgent


def agents_from_json(raw_agents: object) -> dict[str, RunAgent]:
    if not isinstance(raw_agents, str) or not raw_agents.strip():
        return {}
    try:
        parsed = json.loads(raw_agents)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}

    agents: dict[str, RunAgent] = {}
    for raw_agent_id, raw_agent in parsed.items():
        agent_id = str(raw_agent_id).strip()
        if not agent_id or not isinstance(raw_agent, dict):
            continue
        context_id = raw_agent.get("context_id")
        window_start_sequence = raw_agent.get("window_start_sequence")
        window_base = raw_agent.get("window_base")
        agents[agent_id] = RunAgent(
            agent_id=agent_id,
            context_id=context_id if isinstance(context_id, str) else None,
            window_start_sequence=_agent_window_start_sequence(window_start_sequence),
            window_base=window_base if isinstance(window_base, bool) else True,
        )
    return agents


def agents_to_json(agents: dict[str, RunAgent]) -> str:
    return json.dumps(
        {
            agent_id: agent.to_dict()
            for agent_id, agent in agents.items()
        }
    )


def _agent_window_start_sequence(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value
