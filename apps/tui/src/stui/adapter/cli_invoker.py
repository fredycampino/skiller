from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field


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

        return subprocess.run(  # noqa: S603
            command,
            text=True,
            capture_output=True,
            check=False,
            env=os.environ.copy(),
        )
