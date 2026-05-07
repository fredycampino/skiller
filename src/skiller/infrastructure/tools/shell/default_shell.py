import os
import re
import shlex
import subprocess
from pathlib import Path

from skiller.application.ports.execution.shell_port import ShellPort


class DefaultShellRunner(ShellPort):
    _SEGMENT_OPERATORS: set[str] = {"&&", "||", ";", "|"}
    _ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
    _CRITICAL_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"(^|[\s;&|])sudo(\s|$)", re.IGNORECASE),
        re.compile(r"(^|[\s;&|])su(\s|$)", re.IGNORECASE),
        re.compile(r"(^|[\s;&|])shutdown(\s|$)", re.IGNORECASE),
        re.compile(r"(^|[\s;&|])(reboot|halt|poweroff)(\s|$)", re.IGNORECASE),
        re.compile(r"(^|[\s;&|])mkfs(\.[a-z0-9_+-]+)?(\s|$)", re.IGNORECASE),
        re.compile(r"(^|[\s;&|])dd(\s|$)", re.IGNORECASE),
        re.compile(r"rm\s+-rf\s+/(?:\s|$)", re.IGNORECASE),
        re.compile(r"--no-preserve-root", re.IGNORECASE),
        re.compile(r"(^|[\s;&|])kill\s+-9\s+-1(\s|$)", re.IGNORECASE),
        re.compile(r":\(\)\s*\{\s*:\|:\s*&\s*\};:", re.IGNORECASE),
    )

    def __init__(
        self,
        *,
        workspace_root: str | None = None,
        allowlist_enabled: bool = False,
        allowed_commands: list[str] | None = None,
        allow_env_prefix: bool = True,
        sandbox_enabled: bool = False,
    ) -> None:
        if sandbox_enabled:
            raise RuntimeError("shell sandbox is not implemented yet")

        self._workspace_root = self._resolve_workspace_root(workspace_root)
        self._allowlist_enabled = allowlist_enabled
        self._allowed_commands = {
            command.strip()
            for command in (allowed_commands or [])
            if isinstance(command, str) and command.strip()
        }
        self._allow_env_prefix = allow_env_prefix

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
        effective_cwd = self._resolve_cwd(cwd)
        self._validate_command(command=command, effective_cwd=effective_cwd)

        try:
            completed = subprocess.run(
                [shell, "-lc", command],
                capture_output=True,
                text=True,
                cwd=effective_cwd,
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

    def _resolve_workspace_root(self, workspace_root: str | None) -> Path:
        if workspace_root and workspace_root.strip():
            return Path(workspace_root.strip()).expanduser().resolve(strict=False)
        return Path.cwd().resolve(strict=False)

    def _resolve_cwd(self, cwd: str | None) -> str | None:
        if cwd is None:
            return str(self._workspace_root)

        raw = cwd.strip()
        if not raw:
            return str(self._workspace_root)

        requested = Path(raw).expanduser()
        if not requested.is_absolute():
            requested = self._workspace_root / requested
        resolved = requested.resolve(strict=False)
        self._ensure_path_in_workspace(resolved, label="cwd")
        return str(resolved)

    def _validate_command(self, *, command: str, effective_cwd: str | None) -> None:
        normalized = command.strip()
        if not normalized:
            raise ValueError("shell command cannot be empty")

        for pattern in self._CRITICAL_COMMAND_PATTERNS:
            if pattern.search(normalized):
                raise ValueError("shell command blocked by security policy")

        self._validate_allowlist(command=normalized)

        working_directory = Path(effective_cwd or str(self._workspace_root))
        for candidate in self._extract_path_candidates(normalized):
            resolved = self._resolve_candidate_path(candidate, cwd=working_directory)
            if resolved is None:
                continue
            self._ensure_path_in_workspace(resolved, label="command path")

    def _validate_allowlist(self, *, command: str) -> None:
        if not self._allowlist_enabled:
            return

        if not self._allowed_commands:
            raise ValueError("shell command blocked by allowlist policy: empty allowed_commands")

        segments = self._split_command_segments(command)
        for segment in segments:
            executable = self._extract_executable(segment)
            if executable is None:
                raise ValueError(
                    "shell command blocked by allowlist policy: executable could not be resolved"
                )
            if executable not in self._allowed_commands:
                raise ValueError(
                    f"shell command blocked by allowlist policy: '{executable}' is not allowed"
                )

    def _split_command_segments(self, command: str) -> list[list[str]]:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|;&")
        lexer.whitespace_split = True
        lexer.commenters = ""
        try:
            tokens = list(lexer)
        except ValueError as exc:
            raise ValueError(
                "shell command blocked by allowlist policy: command could not be parsed"
            ) from exc

        segments: list[list[str]] = []
        current: list[str] = []
        for token in tokens:
            if token in self._SEGMENT_OPERATORS:
                if current:
                    segments.append(current)
                    current = []
                continue
            current.append(token)
        if current:
            segments.append(current)
        if not segments:
            raise ValueError(
                "shell command blocked by allowlist policy: command does not contain segments"
            )
        return segments

    def _extract_executable(self, tokens: list[str]) -> str | None:
        if not tokens:
            return None

        index = 0
        if self._allow_env_prefix:
            while index < len(tokens) and self._ENV_ASSIGNMENT_RE.match(tokens[index]):
                index += 1

        if index >= len(tokens):
            return None

        raw = tokens[index].strip()
        if not raw:
            return None
        return Path(raw).name

    def _extract_path_candidates(self, command: str) -> list[str]:
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError:
            return self._extract_paths_from_raw_command(command)

        candidates: list[str] = []
        for token in tokens:
            candidates.extend(self._paths_from_token(token))
        return candidates

    def _extract_paths_from_raw_command(self, command: str) -> list[str]:
        candidates: list[str] = []
        for match in re.findall(r"(~?/[^\s'\";|&<>]+|\.\.?/[^\s'\";|&<>]+)", command):
            candidates.append(match)
        return candidates

    def _paths_from_token(self, token: str) -> list[str]:
        raw = token.strip()
        if not raw:
            return []

        stripped = re.sub(r"^[0-9]*[<>]+", "", raw)
        if "=" in stripped:
            _, maybe_path = stripped.split("=", 1)
            return self._path_if_candidate(maybe_path)
        return self._path_if_candidate(stripped)

    def _path_if_candidate(self, value: str) -> list[str]:
        candidate = value.strip().strip("'\"")
        if not candidate:
            return []
        if candidate.startswith("/"):
            return [candidate]
        if candidate.startswith("./") or candidate.startswith("../"):
            return [candidate]
        if candidate.startswith("~"):
            return [candidate]
        return []

    def _resolve_candidate_path(self, candidate: str, *, cwd: Path) -> Path | None:
        if candidate.startswith("/"):
            return Path(candidate).resolve(strict=False)

        expanded = Path(candidate).expanduser()
        if expanded.is_absolute():
            return expanded.resolve(strict=False)

        if candidate.startswith("./") or candidate.startswith("../"):
            return (cwd / expanded).resolve(strict=False)

        return None

    def _ensure_path_in_workspace(self, path: Path, *, label: str) -> None:
        if path == self._workspace_root:
            return
        try:
            path.relative_to(self._workspace_root)
        except ValueError as exc:
            raise ValueError(f"{label} is outside workspace root") from exc
