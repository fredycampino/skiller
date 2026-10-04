import re
import shlex
from collections.abc import Mapping
from pathlib import Path

from skiller.application.tools.shell.command_expander import ShellCommandExpander
from skiller.application.tools.shell.config import ShellToolRuntimeConfig


class ShellCommandPolicy:
    _SEGMENT_OPERATORS: set[str] = {"&&", "||", ";", "|"}
    _ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
    _EXPANSION_START_RE = re.compile(r"\$[A-Za-z_0-9@*#?$!{(\-]")
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
        self.expand_paths = config.expand_paths
        self._command_expander = ShellCommandExpander()

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
        if not resolved.exists():
            raise ValueError(f"shell cwd does not exist: {resolved}")
        if not resolved.is_dir():
            raise ValueError(f"shell cwd is not a directory: {resolved}")
        return str(resolved)

    def validate_command(
        self,
        *,
        command: str,
        effective_cwd: str,
        environment: Mapping[str, str],
    ) -> None:
        normalized = command.strip()
        if not normalized:
            raise ValueError("shell command cannot be empty")

        command_without_heredoc_bodies = self._command_expander.without_heredoc_bodies(
            command=normalized
        )
        for pattern in self._CRITICAL_COMMAND_PATTERNS:
            if pattern.search(command_without_heredoc_bodies):
                raise ValueError("shell command blocked by security policy")

        self._validate_allowlist(command=command_without_heredoc_bodies)

        command_for_path_validation = command_without_heredoc_bodies
        if self.expand_paths:
            command_for_path_validation = self._command_expander.expand(
                command=normalized,
                environment=environment,
            )
        else:
            command_for_path_validation = self._without_dynamic_path_words(
                command_for_path_validation
            )
        working_directory = Path(effective_cwd)
        for candidate in self._extract_path_candidates(command_for_path_validation):
            if candidate == "/dev/null":
                continue
            resolved = self._resolve_candidate_path(candidate, cwd=working_directory)
            if resolved is None:
                continue
            self._ensure_path_allowed(resolved, label="command path")

    def _without_dynamic_path_words(self, command: str) -> str:
        """Mask unresolved words for path checks, preserving literal quote context."""
        words: list[str] = []
        start = 0
        index = 0
        quote: str | None = None
        dynamic = False
        while index < len(command):
            character = command[index]
            if character == "\\" and quote != "'":
                next_character = command[index + 1 : index + 2]
                if quote != '"' or next_character in {"$", "`", '"', "\\", "\n"}:
                    index += 2
                    continue
            if character in {"'", '"'}:
                if quote is None:
                    quote = character
                elif quote == character:
                    quote = None
                index += 1
                continue
            if quote != "'" and (
                character == "`" or self._EXPANSION_START_RE.match(command, index)
            ):
                dynamic = True
            if quote is None and (character.isspace() or character in ";|&<>"):
                word = "__unresolved_path__" if dynamic else command[start:index]
                words.extend((word, character))
                start = index + 1
                dynamic = False
            index += 1
        words.append("__unresolved_path__" if dynamic else command[start:])
        return "".join(words)

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
                allowed = ", ".join(sorted(self.allowed_commands))
                raise ValueError(
                    f"Command '{executable}' is not in the shell allowlist. "
                    f"Use an allowed command ({allowed}) or ask to add "
                    f"'{executable}' to allowed_commands."
                )

    def _split_command_segments(self, command: str) -> list[list[str]]:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|;&")
        lexer.whitespace_split = True
        lexer.commenters = ""
        try:
            tokens = list(lexer)
        except ValueError as exc:
            raise ValueError(
                f"shell command could not be parsed safely: {exc}. "
                "Check quotes and heredoc delimiters."
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
        segments = self._split_command_segments(command)

        candidates: list[str] = []
        for segment in segments:
            for token in self._segment_arguments(segment):
                candidates.extend(self._paths_from_token(token))
        return candidates

    def _segment_arguments(self, tokens: list[str]) -> list[str]:
        index = 0
        env_assignments: list[str] = []
        if self.allow_env_prefix:
            while index < len(tokens) and self._ENV_ASSIGNMENT_RE.match(tokens[index]):
                env_assignments.append(tokens[index])
                index += 1
        if index >= len(tokens):
            return env_assignments
        executable_path = tokens[index].strip().strip("'\"")
        arguments = tokens[index + 1 :]
        executable_candidates = self._path_if_candidate(executable_path)
        return env_assignments + executable_candidates + arguments

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
        return []

    def _resolve_candidate_path(self, candidate: str, *, cwd: Path) -> Path | None:
        if candidate.startswith("/"):
            return Path(candidate).resolve(strict=False)

        if candidate.startswith("./") or candidate.startswith("../"):
            return (cwd / candidate).resolve(strict=False)

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
        raise ValueError(f"shell {label} escapes allowed_paths: {path}")
