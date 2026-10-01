def remove_shell_line_continuations(command: str) -> str:
    """Remove active escaped newlines, preserving single quotes and comments."""
    result: list[str] = []
    quote: str | None = None
    word_start = True
    index = 0
    while index < len(command):
        character = command[index]
        if quote == "'":
            result.append(character)
            if character == quote:
                quote = None
            index += 1
            continue
        if character == "#" and quote is None and word_start:
            end = command.find("\n", index)
            end = len(command) if end == -1 else end
            result.append(command[index:end])
            index = end
            continue
        if character == "\\" and index + 1 < len(command):
            escaped = command[index + 1]
            if escaped == "\n":
                index += 2
                continue
            if quote is None or escaped in '$`"\\':
                result.append(command[index : index + 2])
                word_start = False
                index += 2
                continue
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
        result.append(character)
        word_start = quote is None and character in " \t\n;|&()<>"
        index += 1
    return "".join(result)
