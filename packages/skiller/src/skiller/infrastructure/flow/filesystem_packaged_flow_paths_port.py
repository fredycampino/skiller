from pathlib import Path

from skiller.domain.flow.packaged_flow_paths_port import PackagedFlowPathsPort


class FilesystemPackagedFlowPathsPort(PackagedFlowPathsPort):
    def get_paths(self) -> tuple[Path, ...]:
        module_path = Path(__file__).resolve()

        for parent in module_path.parents:
            flow_path = parent / "apps" / "agents"
            if flow_path.is_dir():
                return (flow_path,)

        raise FileNotFoundError("Packaged flows directory not found: apps/agents")
