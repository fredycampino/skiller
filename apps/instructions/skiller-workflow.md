# Contributing Workflow

Use this instruction when a contributor needs to clone the repository, prepare a
feature or release branch, or open a pull request. The contributor must never
push directly to `main`.

## Access model

There are two supported contribution models:

- A contributor with write access to the repository can push `feature/*` and
  `release/*` branches to the repository.
- A contributor without write or administrator access must fork the repository,
  push branches to their fork, and open a pull request to the canonical
  repository.

Administrator access is not required to contribute code. A maintainer with
write access is responsible for merging the pull request and, for a release,
the repository workflow creates the version tag after the merge.

## Clone and configure remotes

Replace `OWNER` and `REPO` with the canonical repository coordinates.
OWNDER=fredycampino
REPO=skiller

```bash
git clone https://github.com/OWNER/REPO.git
cd REPO
```

## Create a feature PR

Start from the updated `main` branch and use exactly one commit on the branch:

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/SHORT-DESCRIPTION
```

Implement the change, add or update focused tests, and run the same checks used
by CI:

```bash
python scripts/ci/validate_pr_branch.py \
  --base-ref main \
  --expected-base main \
  --head-ref feature/SHORT-DESCRIPTION \
  --head-prefix feature/

python -m ruff check packages/skiller/src apps/tui/src packages/skiller/tests apps/tui/tests
python -m pytest
python -m build
```

Commit the complete change once, then push the branch:

```bash
git add -A
git commit -m "feat: describe the change"
git push -u origin feature/SHORT-DESCRIPTION
```

The branch must be directly on top of the current `origin/main` and contain
one commit. If the branch has extra commits, squash them on the contributor's
own branch before validation and push the rewritten branch with
`git push --force-with-lease`.

Open the PR with the PR agent from the repository root:

```bash
uv run skiller run --file apps/agents/pr/agent.yaml \
  --arg owner=OWNER \
  --arg repo=REPO \
  --arg head=feature/SHORT-DESCRIPTION \
  --arg base=main \
  --arg title="feat: describe the change" \
  --arg body="## Summary
- Describe the user-visible change.

## Validation
- python -m ruff check ...
- python -m pytest
- python -m build"
```

For a fork, set `owner` and `repo` to the canonical repository and use the
fork-qualified head expected by GitHub:

```bash
--arg head=YOUR_USER:feature/SHORT-DESCRIPTION
```

The PR base is always `main`. Do not select a personal fork branch as the base.
The GitHub MCP token used by the agent must be available at
`~/.skiller/secrets/github_mcp_token`.

## Create a release PR

Only create a release branch after the preceding feature work has been merged
and `main` has been updated locally. Replace `VERSION` with the exact package
version, for example `0.1.0-beta.25`:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c release/VERSION
```

Prepare the release with these rules:

- Set `[project].version` in `pyproject.toml` to `VERSION`.
- Move the meaningful entries from `## Unreleased` into a new
  `## VERSION - YYYY-MM-DD` section in `CHANGELOG.md`.
- Leave `## Unreleased` empty or with its existing placeholder.
- Change only `CHANGELOG.md` and `pyproject.toml`.

Run the release-specific and general checks:

```bash
python scripts/ci/validate_pr_branch.py \
  --base-ref main \
  --expected-base main \
  --head-ref release/VERSION \
  --head-prefix release/

python scripts/ci/validate_release_pr.py \
  --base-ref main \
  --expected-base main \
  --head-ref release/VERSION

python -m ruff check packages/skiller/src apps/tui/src packages/skiller/tests apps/tui/tests
python -m pytest
python -m build
```

Create one release commit and push it:

```bash
git add CHANGELOG.md pyproject.toml
git commit -m "release: VERSION"
git push -u origin release/VERSION
```

Open the release PR with the same PR agent, using `release/VERSION` as `head`
for a branch in the canonical repository, or
`YOUR_USER:release/VERSION` for a fork:

```bash
uv run skiller run --file apps/agents/pr/agent.yaml \
  --arg owner=OWNER \
  --arg repo=REPO \
  --arg head=release/VERSION \
  --arg base=main \
  --arg title="release: VERSION" \
  --arg body="## Summary
- Prepare release VERSION.

## Validation
- validate_pr_branch.py passed
- validate_release_pr.py passed
- ruff check passed
- pytest passed
- python -m build passed"
```

After the release PR is merged, do not create the tag manually. The release
workflow creates and pushes `vVERSION` from the merge commit. A maintainer must
resolve branch protection, merge conflicts, required checks, or permission
errors when the contributor cannot do so.

## PR checklist

Before opening either PR, confirm:

- `git status` is clean except for the intended commit.
- The branch starts with the required prefix: `feature/` or `release/`.
- The PR base is `main`.
- The branch is exactly one commit directly on top of `origin/main`.
- The PR body lists the relevant checks and any known limitations.
- No secrets, credentials, generated local files, or unrelated changes are included.
