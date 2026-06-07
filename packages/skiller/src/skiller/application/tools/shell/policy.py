import re
import shlex
from pathlib import Path

from skiller.application.tools.shell.config import ShellToolRuntimeConfig


class ShellCommandPolicy:
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
        config: ShellToolRuntimeConfig,
    ) -> None:
        self.allowed_roots = self._resolve_allowed_roots(config.allowed_paths)
        self.allowlist_enabled = config.allowlist_enabled
        self.allowed_commands = {
            command.strip()
            for command in config.allowed_commands
            if isinstance(command, str) and command.strip()
        }
        self.allow_env_prefix = config.allow_env_prefix

    def resolve_cwd(self, cwd: str | None) -> str:
        if cwd is None:
            return str(self.allowed_roots[0])

        raw = cwd.strip()
        if not raw:
            return str(self.allowed_roots[0])

        requested = Path(raw).expanduser()
        if not requested.is_absolute():
            requested = self.allowed_roots[0] / requested
        resolved = requested.resolve(strict=False)
        self._ensure_path_allowed(resolved, label="cwd")
        return str(resolved)

    def validate_command(self, *, command: str, effective_cwd: str) -> None:
        normalized = command.strip()
        if not normalized:
            raise ValueError("shell command cannot be empty")

        for pattern in self._CRITICAL_COMMAND_PATTERNS:
            if pattern.search(normalized):
                raise ValueError("shell command blocked by security policy")

        self._validate_allowlist(command=normalized)

        working_directory = Path(effective_cwd)
        for candidate in self._extract_path_candidates(normalized):
            if candidate == "/dev/null":
                continue
            resolved = self._resolve_candidate_path(candidate, cwd=working_directory)
            if resolved is None:
                continue
            self._ensure_path_allowed(resolved, label="command path")

    def _resolve_allowed_roots(self, allowed_paths: tuple[Path, ...]) -> tuple[Path, ...]:
        if allowed_paths:
            return allowed_paths
        return (Path.cwd().resolve(strict=False),)

    def _validate_allowlist(self, *, command: str) -> None:
        if not self.allowlist_enabled:
            return

        if not self.allowed_commands:
            raise ValueError("shell command blocked by allowlist policy: empty allowed_commands")

        for segment in self._split_command_segments(command):
            executable = self._extract_executable(segment)
            if executable is None:
                raise ValueError(
                    "shell command blocked by allowlist policy: executable could not be resolved"
                )
            if executable not in self.allowed_commands:
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
        index = 0
        if self.allow_env_prefix:
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
            segments = self._split_command_segments(command)
        except ValueError:
            return self._extract_paths_from_raw_command(command)

        candidates: list[str] = []
        for segment in segments:
            for token in self._segment_arguments(segment):
                candidates.extend(self._paths_from_token(token))
        return candidates

    def _segment_arguments(self, tokens: list[str]) -> list[str]:
        index = 0
        if self.allow_env_prefix:
            while index < len(tokens) and self._ENV_ASSIGNMENT_RE.match(tokens[index]):
                index += 1
        if index >= len(tokens):
            return []
        return tokens[index + 1 :]

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

    def _ensure_path_allowed(self, path: Path, *, label: str) -> None:
        for root in self.allowed_roots:
            if path == root:
                return
            try:
                path.relative_to(root)
                return
            except ValueError:
                continue
        raise ValueError(f"shell {label} escapes allowed_paths")
