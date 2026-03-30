import os
import subprocess
from pathlib import Path

from skiller.application.ports.shell_port import ShellPort


class DefaultShellRunner(ShellPort):
    def run(
        self,
        *,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | float | None = None,
    ) -> dict[str, object]:
        shell = self._resolve_shell()
        merged_env = dict(os.environ)
        if env:
            merged_env.update(env)

        try:
            completed = subprocess.run(
                [shell, "-lc", command],
                capture_output=True,
                text=True,
                cwd=cwd or None,
                env=merged_env,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            timeout_label = self._format_timeout(timeout)
            raise TimeoutError(f"Shell command timed out after {timeout_label}") from exc

        return {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    def _resolve_shell(self) -> str:
        env_shell = os.getenv("SHELL", "").strip()
        if env_shell and Path(env_shell).is_file() and os.access(env_shell, os.X_OK):
            return env_shell

        for candidate in ("/bin/bash", "/bin/sh"):
            if Path(candidate).is_file() and os.access(candidate, os.X_OK):
                return candidate

        raise RuntimeError("No executable shell found. Tried $SHELL, /bin/bash and /bin/sh")

    def _format_timeout(self, timeout: int | float | None) -> str:
        if isinstance(timeout, int):
            return f"{timeout}s"
        if isinstance(timeout, float):
            return f"{timeout:g}s"
        return "unknown timeout"
