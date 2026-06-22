import tomllib
from pathlib import Path


def test_wheel_includes_agents_and_docs() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    force_include = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"][
        "force-include"
    ]

    assert force_include["packages/skiller/agents"] == "skiller/agents"
    assert force_include["packages/skiller/docs"] == "skiller/docs"
