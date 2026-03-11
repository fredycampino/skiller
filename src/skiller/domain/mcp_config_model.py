from dataclasses import dataclass, field


@dataclass(frozen=True)
class RenderedMcpConfig:
    name: str
    transport: str
    url: str | None = None
    command: str | None = None
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
