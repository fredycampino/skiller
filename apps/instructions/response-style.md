## Response Style

### Progress Updates

Keep progress updates short and concrete. State what is being inspected, changed, or verified.

### Final Answer

Keep the final answer short and compact. State what changed, what was verified, and what remains. Avoid Markdown layouts that create many blank paragraph separators in persisted transcripts. Prefer dense prose and tight bullets over spaced-out sections.

### Transcript Density

Optimize answers for compact transcript reading.

- Avoid blank lines between every sentence.
- Do not separate short bullets with blank lines.
- Prefer compact paragraphs of 2-4 related sentences over many one-line paragraphs.
- Do not use fenced code blocks for formulas, labels, short commands, or single-line examples.
- Use fenced blocks only for real multi-line code, logs, diffs, JSON, YAML, or command output.
- Prefer `label: value` lines for short structured facts.
- Do not create section headers unless they materially improve scanning.
- Keep final answers compact by default; expand only when the user asks for detail.

### Markdown Formatting

Use inline code only for short commands, paths, symbols, and identifiers.

Use fenced code blocks only for real multi-line code, command blocks, config, logs, or diffs.

Do not use fenced code blocks to emphasize isolated one-line phrases in normal prose.
