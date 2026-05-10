# Repo Workflow

Use this repo flow unless the user says otherwise.

## Feature Workflow

1. `[Agent, User]` Work on `feature/<topic>` from `main`.
2. `[Agent]` Implement the feature on that branch.
3. `[Agent]` Validate locally with the repo commands:
   - `./.venv/bin/ruff check .`
   - `./.venv/bin/pytest`
   - `./.venv/bin/python -m hatchling build`
4. `[Agent]` Make sure the working tree is intentional before rewriting history.
   - `git status -sb` must be understandable.
   - If there are accidental unstaged changes, resolve them before the squash.
5. `[Agent]` Squash the branch into one clean commit on top of `main`.
6. `[Agent]` Verify the branch compares against `main` as exactly one commit.
   - `git rev-list --count main..HEAD` must return `1`.
   - `git log --oneline main..HEAD` must show the single PR commit.
7. `[Agent]` If the branch history changed, update the remote branch.
   - Use `git push --force-with-lease origin feature/<topic>` after a squash or other rewrite.
8. `[Agent]` Open the PR from `feature/<topic>` into `main` using `skiller run pr` with explicit inputs.
9. `[Workflow]` The `Feature PR` workflow validates:
   - branch base is `main`
   - branch name starts with `feature/`
   - branch compares as one commit directly on top of `main`
   - `ruff`
   - `pytest`
   - package build
10. `[User]` Review and approve the PR.
11. `[Admin]` Merge the PR into `main`.

## Release Workflow

1. `[Agent, User]` Create `release/<version>` from `main`.
2. `[Agent]` Update `project.version` in `pyproject.toml`.
3. `[Agent]` Update `CHANGELOG.md` with the release summary.
4. `[Agent]` Close the changelog entry as `## <version> - <date>` and reset `## Unreleased`.
5. `[Agent]` Validate locally with the repo commands:
   - `./.venv/bin/ruff check .`
   - `./.venv/bin/pytest`
   - `./.venv/bin/python -m hatchling build`
6. `[Agent]` Make sure the working tree is intentional before rewriting history.
   - `git status -sb` must be understandable.
7. `[Agent]` Squash the branch into one clean commit on top of `main`.
8. `[Agent]` Verify the branch compares against `main` as exactly one commit.
   - `git rev-list --count main..HEAD` must return `1`.
9. `[Agent]` Verify the release branch changes only:
   - `pyproject.toml`
   - `CHANGELOG.md`
10. `[Agent]` If the branch history changed, update the remote branch.
   - Use `git push --force-with-lease origin release/<version>` after a squash or other rewrite.
11. `[Agent]` Open the PR from `release/<version>` into `main` using `skiller run pr` with explicit inputs.
12. `[Workflow]` The `Release PR` workflow validates:
   - branch base is `main`
   - branch name starts with `release/`
   - branch compares as one commit directly on top of `main`
   - only `pyproject.toml` and `CHANGELOG.md` changed
   - `CHANGELOG.md` has a closed section for `<version>`
   - `CHANGELOG.md` resets `Unreleased`
   - `project.version` in `pyproject.toml` matches `<version>`
   - `ruff`
   - `pytest`
   - package build
13. `[User]` Review and approve the PR.
14. `[Admin]` Merge the PR into `main`.
15. `[Workflow]` After merge, CI creates the tag `v<version>` on the merged commit.

## PR Command

The internal `pr` agent does not infer repo metadata or PR fields by itself.
Pass the inputs explicitly with `--arg`.

Feature PR template:

```bash
./.venv/bin/skiller run pr \
  --arg owner=<github-owner> \
  --arg repo=<github-repo> \
  --arg head=feature/<topic> \
  --arg base=main \
  --arg title='<commit-or-pr-title>' \
  --arg body='<short summary and validation>'
```

Release PR template:

```bash
./.venv/bin/skiller run pr \
  --arg owner=<github-owner> \
  --arg repo=<github-repo> \
  --arg head=release/<version> \
  --arg base=main \
  --arg title='release: <version>' \
  --arg body='<release summary and validation>'
```

Practical notes:
- Derive `owner` and `repo` from `git remote get-url origin` if needed.
- If the branch was renamed for workflow compliance, push the new branch before opening the PR.
- If the old remote branch is no longer needed after a rename, delete it explicitly.
- If `pr` fails with unresolved placeholders such as `{{inputs.owner}}`, rerun it with explicit `--arg` inputs.

## Rules

- Do not use a manual release workflow on `main`; that flow is obsolete.
- Do not update `CHANGELOG.md` on feature branches unless the user explicitly asks for it.
- Do not open a release PR with extra file changes.
- Do not leave a feature or release branch as multiple commits when the workflow requires one clean commit.
- Do not open a PR from a branch whose name does not match the required prefix.
- Do not assume a local squash is enough; after rewriting history, verify the remote branch too.
- Do not read or inspect tokens, secrets, or `.env` contents directly.
- Use trusted repo commands that consume credentials implicitly for their normal operation, for example `skiller run pr`.
- If a trusted repo command depends on authenticated environment that is not available in the sandbox, ask permission and run that command outside the sandbox instead of trying it inside the sandbox first.
- Do not use ad hoc scripts or generic tooling around credentials when a trusted repo command already exists for the task.
- If a trusted repo command cannot authenticate because the required environment is missing, report that as a blocker.
