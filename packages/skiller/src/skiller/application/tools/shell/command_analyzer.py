import re
from dataclasses import dataclass

from skiller.application.tools.shell.source import remove_shell_line_continuations


@dataclass(frozen=True)
class ShellCommandSegment:
    executable: str
    has_env_prefix: bool


@dataclass(frozen=True)
class ShellCommandAnalysis:
    segments: tuple[ShellCommandSegment, ...]


@dataclass(frozen=True)
class _ShellToken:
    value: str
    literal: bool
    operator: bool
    quoted: bool
    assignment: bool


class ShellCommandAnalyzer:
    """Analyze a deliberately restricted outer shell language, not arbitrary Bash."""

    _ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
    _RESERVED = frozenset(
        "time ! coproc if then elif else fi for select while until do done "
        "case in esac function { } [[ ]]".split()
    )
    _SEPARATORS = frozenset({"\n", ";", "|", "&&", "||"})
    _REDIRECTIONS = frozenset({"<", ">", ">>", "<&", ">&", "<<", "<<-"})

    def analyze(self, command: str) -> ShellCommandAnalysis:
        segments: list[ShellCommandSegment] = []
        words: list[_ShellToken] = []
        source = remove_shell_line_continuations(command)
        for token in self._tokenize(source):
            if token.operator and token.value in self._SEPARATORS:
                if words:
                    segments.append(self._analyze_segment(words))
                    words = []
                continue
            words.append(token)
        if words:
            segments.append(self._analyze_segment(words))
        if not segments:
            raise ValueError("shell command does not contain executable segments")
        return ShellCommandAnalysis(segments=tuple(segments))

    def _analyze_segment(self, tokens: list[_ShellToken]) -> ShellCommandSegment:
        index = 0
        while index < len(tokens) and tokens[index].assignment:
            index += 1
        has_env_prefix = index > 0
        if index == len(tokens):
            raise ValueError("shell command executable could not be resolved")
        executable = tokens[index]
        if executable.operator or (
            executable.value.isdigit() and index + 1 < len(tokens) and tokens[index + 1].operator
        ):
            raise ValueError("shell command uses unsupported initial redirection")
        if not executable.quoted and executable.value in self._RESERVED:
            raise ValueError("shell command uses unsupported executable shell syntax")
        if not executable.literal or not executable.value:
            raise ValueError("shell command requires a literal executable")
        index += 1
        while index < len(tokens):
            token = tokens[index]
            if not token.operator:
                index += 1
                continue
            if token.value not in self._REDIRECTIONS or index + 1 == len(tokens):
                raise ValueError("shell command uses unsupported redirection")
            target = tokens[index + 1]
            if target.operator:
                raise ValueError("shell command has invalid redirection target")
            if token.value in {"<&", ">&"} and (
                not target.literal or not (target.value.isdigit() or target.value == "-")
            ):
                raise ValueError("shell command requires a literal descriptor redirection")
            index += 2
        return ShellCommandSegment(executable.value, has_env_prefix)

    def _tokenize(self, command: str) -> list[_ShellToken]:
        tokens: list[_ShellToken] = []
        index = 0
        while index < len(command):
            character = command[index]
            if character in " \t\r":
                index += 1
                continue
            if command.startswith("\\\n", index):
                index += 2
                continue
            if character == "#":
                end = command.find("\n", index)
                index = len(command) if end == -1 else end
                continue
            if character in "\n;|&<>":
                operator = character
                for candidate in (
                    "&>>",
                    "<<<",
                    "<<-",
                    "&&",
                    "||",
                    "|&",
                    "&>",
                    ">>",
                    "<<",
                    ">&",
                    "<&",
                    ";;",
                    ";&",
                    "<>",
                    ">|",
                ):
                    if command.startswith(candidate, index):
                        operator = candidate
                        break
                if operator not in self._SEPARATORS | self._REDIRECTIONS:
                    raise ValueError("shell command uses unsupported executable shell syntax")
                tokens.append(_ShellToken(operator, True, True, False, False))
                index += len(operator)
                continue
            token, next_index = self._read_word(command, index)
            if next_index <= index:
                raise ValueError("shell command tokenizer could not advance safely")
            index = next_index
            tokens.append(token)
        return tokens

    def _read_word(self, command: str, index: int) -> tuple[_ShellToken, int]:
        start = index
        value: list[str] = []
        quote: str | None = None
        quoted = False
        literal = True
        while index < len(command):
            character = command[index]
            if quote == "'":
                if character == quote:
                    quote = None
                else:
                    value.append(character)
                index += 1
                continue
            if character == "\\":
                if index + 1 == len(command):
                    raise ValueError("shell command has trailing escape")
                escaped = command[index + 1]
                if quote == '"' and escaped not in '$`"\\\n':
                    value.append(character)
                    index += 1
                    continue
                if escaped != "\n":
                    value.append(escaped)
                    quoted = True
                index += 2
                continue
            if character == "`" or command.startswith("$(", index):
                raise ValueError("shell command uses unsupported command substitution")
            if quote is None and command[index : index + 2] in {"<(", ">("}:
                raise ValueError("shell command uses unsupported process substitution")
            if quote is None and character in "()":
                raise ValueError("shell command uses unsupported executable shell syntax")
            if quote is None and (character in " \t\r\n;|&<>"):
                break
            if character in {"'", '"'}:
                if quote is None:
                    quote = character
                    quoted = True
                    index += 1
                    continue
                if quote == character:
                    quote = None
                    index += 1
                    continue
            if character == "$" or (quote is None and character in "~*?[{}"):
                literal = False
            value.append(character)
            index += 1
        if quote is not None:
            raise ValueError("shell command has unclosed quotation")
        source = command[start:index].replace("\\\n", "")
        assignment = self._ASSIGNMENT.match(source) is not None
        word = "".join(value)
        token = _ShellToken(word, literal, False, quoted, assignment)
        return token, index
