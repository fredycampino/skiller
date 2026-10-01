import re
import shlex
from collections.abc import Mapping


class ShellCommandExpander:
    _VARIABLE_REFERENCE_RE = re.compile(
        r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))"
    )
    _WORD_BOUNDARIES = frozenset(";|&()<>")

    def without_heredoc_bodies(self, *, command: str) -> str:
        sanitized: list[str] = []
        pending_delimiters: list[tuple[str, bool]] = []
        quote: str | None = None
        word_start = True
        index = 0

        while index < len(command):
            character = command[index]
            if character == "\\" and quote != "'":
                escaped = command[index : index + 2]
                sanitized.append(escaped)
                index += len(escaped)
                if escaped != "\\\n":
                    word_start = False
                continue
            if quote is not None:
                sanitized.append(character)
                if character == quote:
                    quote = None
                index += 1
                continue
            if character in {"'", '"'}:
                quote = character
                word_start = False
                sanitized.append(character)
                index += 1
                continue
            if character == "#" and word_start:
                end = command.find("\n", index)
                index = len(command) if end == -1 else end
                continue
            if command.startswith("<<<", index):
                sanitized.append("<<<")
                index += 3
                word_start = True
                continue
            if command.startswith("<<", index):
                start = index
                index += 2
                strip_tabs = command[index : index + 1] == "-"
                if strip_tabs:
                    index += 1
                while command[index : index + 1] in {" ", "\t"}:
                    index += 1
                raw, index, quoted = self._read_heredoc_delimiter(line=command, start=index)
                delimiter = self._remove_shell_quotes(raw_delimiter=raw)
                if not quoted:
                    raise ValueError(
                        "shell command uses unsupported unquoted heredoc delimiter: "
                        f"{delimiter}. Quote the delimiter to make the body literal."
                    )
                pending_delimiters.append((delimiter, strip_tabs))
                sanitized.append(command[start:index])
                word_start = False
                continue
            sanitized.append(character)
            index += 1
            word_start = character.isspace() or character in self._WORD_BOUNDARIES
            if character != "\n" or not pending_delimiters:
                continue
            for delimiter, strip_tabs in pending_delimiters:
                while True:
                    if index >= len(command):
                        raise ValueError(f"shell command has unterminated heredoc: {delimiter}")
                    end = command.find("\n", index)
                    end = len(command) if end == -1 else end + 1
                    line = command[index:end]
                    index = end
                    candidate = line.removesuffix("\n")
                    if strip_tabs:
                        candidate = candidate.lstrip("\t")
                    sanitized.append(self._line_ending(line))
                    if candidate == delimiter:
                        break
            pending_delimiters.clear()

        if pending_delimiters:
            delimiter, _ = pending_delimiters[0]
            raise ValueError(f"shell command has unterminated heredoc: {delimiter}")
        return "".join(sanitized)

    def expand(self, *, command: str, environment: Mapping[str, str]) -> str:
        command_without_heredoc_bodies = self.without_heredoc_bodies(command=command)
        tilde_expanded = self._expand_tilde_references(
            command=command_without_heredoc_bodies,
            environment=environment,
        )
        return self._expand_variable_references(
            command=tilde_expanded,
            environment=environment,
        )

    def _read_heredoc_delimiter(self, *, line: str, start: int) -> tuple[str, int, bool]:
        delimiter: list[str] = []
        quote: str | None = None
        delimiter_quoted = False
        index = start

        while index < len(line):
            character = line[index]
            if quote is None and (character.isspace() or character in ";|&<>"):
                break
            if quote is None and character == "$":
                next_index = index + 1
                while line.startswith("\\\n", next_index):
                    next_index += 2
                if line[next_index : next_index + 1] in {"'", '"'}:
                    raise ValueError(
                        "shell command uses unsupported dollar-quoted heredoc delimiter"
                    )
            if character == "\\" and quote == '"':
                raise ValueError(
                    "shell command uses unsupported escape in double-quoted heredoc delimiter"
                )
            delimiter.append(character)
            if character == "\\" and quote != "'":
                delimiter_quoted = True
                index += 1
                if index < len(line):
                    delimiter.append(line[index])
            elif character in {"'", '"'}:
                delimiter_quoted = True
                if quote is None:
                    quote = character
                elif quote == character:
                    quote = None
            index += 1

        raw_delimiter = "".join(delimiter)
        if quote is not None:
            raise ValueError(
                "shell command could not be parsed safely: No closing quotation. "
                "Check quotes and heredoc delimiters."
            )
        if not raw_delimiter:
            raise ValueError("shell command has invalid heredoc delimiter")
        return raw_delimiter, index, delimiter_quoted

    def _remove_shell_quotes(self, *, raw_delimiter: str) -> str:
        try:
            parts = shlex.split(raw_delimiter, posix=True)
        except ValueError as exc:
            raise ValueError(f"shell command has invalid heredoc delimiter: {exc}") from exc
        if len(parts) != 1 or not parts[0]:
            raise ValueError("shell command has invalid heredoc delimiter")
        return parts[0]

    def _line_ending(self, line: str) -> str:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
        return ""

    def _expand_tilde_references(
        self,
        *,
        command: str,
        environment: Mapping[str, str],
    ) -> str:
        expanded: list[str] = []
        quote: str | None = None
        word_start = True
        index = 0

        while index < len(command):
            character = command[index]
            if character == "\\":
                expanded.append(character)
                index += 1
                if index < len(command):
                    expanded.append(command[index])
                    index += 1
                word_start = False
                continue

            if character in {"'", '"'}:
                if quote is None:
                    quote = character
                elif quote == character:
                    quote = None
                expanded.append(character)
                index += 1
                word_start = False
                continue

            if quote is None and character.isspace():
                expanded.append(character)
                index += 1
                word_start = True
                continue

            if quote is None and character in self._WORD_BOUNDARIES:
                expanded.append(character)
                index += 1
                word_start = True
                continue

            if quote is None and word_start and character == "~":
                reference_end = self._tilde_reference_end(command=command, start=index)
                reference = command[index:reference_end]
                expanded.append(
                    self._resolve_tilde_reference(
                        reference=reference,
                        environment=environment,
                    )
                )
                index = reference_end
                word_start = False
                continue

            expanded.append(character)
            index += 1
            word_start = character == "="

        return "".join(expanded)

    def _tilde_reference_end(self, *, command: str, start: int) -> int:
        index = start + 1
        while index < len(command):
            character = command[index]
            if character == "/" or character.isspace():
                break
            if character in self._WORD_BOUNDARIES:
                break
            index += 1
        return index

    def _resolve_tilde_reference(
        self,
        *,
        reference: str,
        environment: Mapping[str, str],
    ) -> str:
        if reference != "~":
            raise ValueError(f"shell command uses unsupported tilde expansion: {reference}")

        home = environment.get("HOME")
        if not home:
            raise ValueError("shell command cannot expand '~': HOME is not set")
        return shlex.quote(home)

    def _expand_variable_references(
        self,
        *,
        command: str,
        environment: Mapping[str, str],
    ) -> str:
        expanded: list[str] = []
        quote: str | None = None
        index = 0

        while index < len(command):
            character = command[index]
            if character == "\\":
                expanded.append(character)
                index += 1
                if index < len(command):
                    expanded.append(command[index])
                    index += 1
                continue

            if character in {"'", '"'}:
                if quote is None:
                    quote = character
                elif quote == character:
                    quote = None
                expanded.append(character)
                index += 1
                continue

            variable_match = None
            if character == "$" and quote != "'":
                variable_match = self._VARIABLE_REFERENCE_RE.match(command, index)
            if variable_match is None:
                expanded.append(character)
                index += 1
                continue

            variable_name = variable_match.group(1) or variable_match.group(2)
            value = environment.get(variable_name, "")
            expanded.append(self._prepare_variable_value(value=value, quote=quote))
            index = variable_match.end()

        return "".join(expanded)

    def _prepare_variable_value(self, *, value: str, quote: str | None) -> str:
        if quote == '"':
            return value.replace("\\", "\\\\").replace('"', '\\"')

        fields = re.split(r"(\s+)", value)
        return "".join(field if field.isspace() else shlex.quote(field) for field in fields)
