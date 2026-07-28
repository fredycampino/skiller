from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from skiller.application.tools.files.config import FilesToolRuntimeConfig
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.domain.agent.config.port import AgentConfigPort
from skiller.domain.run.run_agent_store_port import RunAgentStorePort
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.runner_port import RunnerPort
from skiller.domain.tool.tool_contract import ToolRuntimeConfigs


class GetAgentToolsStatus(str, Enum):
    OK = "OK"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"


@dataclass(frozen=True)
class ShellToolsConfigItem:
    enabled: bool
    allowed_paths: tuple[Path, ...] = ()
    allowlist_enabled: bool = False
    allow_env_prefix: bool = True
    allowed_commands: tuple[str, ...] = ()


@dataclass(frozen=True)
class FilesToolsConfigItem:
    enabled: bool
    read: tuple[Path, ...] = ()
    write: tuple[Path, ...] = ()
    all: tuple[Path, ...] = ()


@dataclass(frozen=True)
class AgentToolsConfig:
    shell: ShellToolsConfigItem
    files: FilesToolsConfigItem


@dataclass(frozen=True)
class GetAgentToolsResult:
    status: GetAgentToolsStatus
    run_id: str
    agent_id: str | None = None
    source: str | None = None
    ref: str | None = None
    config_path: Path | None = None
    cwd: Path | None = None
    tools: AgentToolsConfig | None = None
    error: str | None = None


class GetAgentToolsUseCase:
    def __init__(
        self,
        *,
        run_store: RunStorePort,
        run_agent_store: RunAgentStorePort,
        agent_config: AgentConfigPort,
        skill_runner: RunnerPort,
    ) -> None:
        self.run_store = run_store
        self.run_agent_store = run_agent_store
        self.agent_config = agent_config
        self.skill_runner = skill_runner

    def execute(self, run_id: str) -> GetAgentToolsResult:
        if not run_id:
            raise RuntimeError("GetAgentToolsUseCase requires run_id")

        run = self.run_store.get_run(run_id)
        if run is None:
            return GetAgentToolsResult(
                status=GetAgentToolsStatus.RUN_NOT_FOUND,
                run_id=run_id,
                error=f"Run '{run_id}' not found",
            )

        agent = self.run_agent_store.get_first_agent(run_id=run_id)
        if agent is None:
            return GetAgentToolsResult(
                status=GetAgentToolsStatus.AGENT_NOT_FOUND,
                run_id=run_id,
                source=run.source,
                ref=run.ref,
                error=f"Run '{run_id}' has no attached agents",
            )

        config_path = self._resolve_agent_config_path(run.source, run.ref)
        config = self.agent_config.get_config(config_path=config_path)
        return GetAgentToolsResult(
            status=GetAgentToolsStatus.OK,
            run_id=run_id,
            agent_id=agent.agent_id,
            source=run.source,
            ref=run.ref,
            config_path=config_path,
            cwd=Path.cwd(),
            tools=_build_tools_config(config.tools),
        )

    def _resolve_agent_config_path(self, source: str, ref: str) -> Path | None:
        try:
            config_path = self.skill_runner.resolve_file_path(source, ref, "agent.json")
        except (FileNotFoundError, ValueError):
            return None

        if config_path.exists():
            return config_path
        return None


def _build_tools_config(configs: ToolRuntimeConfigs) -> AgentToolsConfig:
    shell = configs.get("shell")
    files = configs.get("files")
    return AgentToolsConfig(
        shell=_build_shell_config(shell),
        files=_build_files_config(files),
    )


def _build_shell_config(config: object | None) -> ShellToolsConfigItem:
    if not isinstance(config, ShellToolRuntimeConfig):
        return ShellToolsConfigItem(enabled=False)
    return ShellToolsConfigItem(
        enabled=True,
        allowed_paths=config.allowed_paths,
        allowlist_enabled=config.allowlist_enabled,
        allow_env_prefix=config.allow_env_prefix,
        allowed_commands=config.allowed_commands,
    )


def _build_files_config(config: object | None) -> FilesToolsConfigItem:
    if not isinstance(config, FilesToolRuntimeConfig):
        return FilesToolsConfigItem(enabled=False)
    return FilesToolsConfigItem(
        enabled=True,
        read=config.read,
        write=config.write,
        all=config.all,
    )
