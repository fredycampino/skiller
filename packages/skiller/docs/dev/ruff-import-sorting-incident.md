# Ruff Import Sorting Incident

## Summary

GitHub Actions reported repeated `I001` import sorting failures even after local
`ruff --fix` appeared to pass.

The failing workflow used the same commit as the local branch and ran:

```bash
python -m ruff check packages/skiller/src apps/tui/src packages/skiller/tests apps/tui/tests
```

## Cause

Ruff import sorting depended on environment-specific first-party package
detection. The repository contains two source roots:

- `packages/skiller/src/skiller`
- `apps/tui/src/stui`

Without explicit `known-first-party`, local and CI import classification could
diverge for `skiller` and `stui` imports.

## Fix

Make first-party packages explicit in `pyproject.toml`:

```toml
[tool.ruff.lint.isort]
known-first-party = ["skiller", "stui"]
```

Then run the exact CI command with `--fix`:

```bash
python -m ruff check --fix packages/skiller/src apps/tui/src packages/skiller/tests apps/tui/tests
python -m ruff check packages/skiller/src apps/tui/src packages/skiller/tests apps/tui/tests
```

## Lesson

For monorepos with multiple import roots, do not rely on Ruff/isort heuristics
for first-party packages. Configure them explicitly and validate with the exact
CI command.
