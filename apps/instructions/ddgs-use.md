## DDGS: Search and Documents

### 1. Installation

The user must choose **pipx** or **venv**. Do not install without their approval.

With pipx (already installed):
```bash
pipx install ddgs
pipx ensurepath
```
Open a new terminal if `ddgs` is not on PATH.

With venv:
```bash
python3 -m venv .venv-ddgs
source .venv-ddgs/bin/activate
python -m pip install ddgs
```

### 2. Basic Search

```bash
ddgs text --query "OpenAI reasoning documentation" --max_results 5
```
Returns titles, links, and snippets—not full documents.

### 3. Retrieve Documents as Markdown

Use a result URL; it does not need to end in `.md`:
```bash
ddgs extract --url "https://developers.openai.com/api/docs/guides/reasoning" --format text_markdown
```
DDGS retrieves and converts content to Markdown. It may include menus and navigation; limit the output for large documents.

Help: `ddgs --help`, `ddgs text --help`, and `ddgs extract --help`.
