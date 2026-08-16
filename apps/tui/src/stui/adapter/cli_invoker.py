from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CliInvoker:
    module_name: str = "skiller"
    python_executable: str = field(default_factory=lambda: sys.executable)

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = [
            self.python_executable,
            "-m",
            self.module_name,
            *args,
        ]
        environment = os.environ.copy()
        source_paths = _workspace_source_paths()
        if source_paths:
            current_pythonpath = environment.get("PYTHONPATH", "")
            pythonpath_entries = [str(path) for path in source_paths]
            if current_pythonpath:
                pythonpath_entries.append(current_pythonpath)
            environment["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)

        return subprocess.run(  # noqa: S603
            command,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )


def _workspace_source_paths() -> tuple[Path, ...]:
    for parent in Path(__file__).resolve().parents:
        runtime_source = parent / "packages" / "skiller" / "src"
        tui_source = parent / "apps" / "tui" / "src"
        if runtime_source.is_dir() and tui_source.is_dir():
            return runtime_source, tui_source
    return ()
