from typing import Any, Protocol


class SkillRunnerPort(Protocol):
    def load_skill(self, skill_source: str, skill_ref: str) -> dict[str, Any]: ...

    def render_step(self, step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]: ...

    def read_skill_file(
        self,
        skill_source: str,
        skill_ref: str,
        file_ref: str,
    ) -> str: ...
