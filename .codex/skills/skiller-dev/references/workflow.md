# Repo Workflow

Use this repo flow unless the user says otherwise.

## Feature Workflow

1. `[Agent, User]` Work on `feature/<topic>` from `main`.
2. `[Agent]` Implement the feature on that branch.
3. `[Agent]` Validate locally:
   - `ruff`
   - `pytest`
   - package build
4. `[Agent]` Squash the branch into one clean commit on top of `main`.
5. `[Agent]` Verify the branch compares against `main` as exactly one commit.
6. `[Agent]` Open the PR from `feature/<topic>` into `main` using `skiller run pull_request`.
7. `[Workflow]` The `Feature PR` workflow validates:
   - branch base is `main`
   - branch name starts with `feature/`
   - branch compares as one commit directly on top of `main`
   - `ruff`
   - `pytest`
   - package build
8. `[User]` Review and approve the PR.
9. `[Admin]` Merge the PR into `main`.

## Release Workflow

1. `[Agent, User]` Create `release/<version>` from `main`.
2. `[Agent]` Update `project.version` in `pyproject.toml`.
3. `[Agent]` Update `CHANGELOG.md` with the release summary.
4. `[Agent]` Close the changelog entry as `## <version> - <date>` and reset `## Unreleased`.
5. `[Agent]` Validate locally:
   - `ruff`
   - `pytest`
   - package build
6. `[Agent]` Squash the branch into one clean commit on top of `main`.
7. `[Agent]` Verify the branch compares against `main` as exactly one commit.
8. `[Agent]` Verify the release branch changes only:
   - `pyproject.toml`
   - `CHANGELOG.md`
9. `[Agent]` Open the PR from `release/<version>` into `main` using `skiller run pull_request`.
10. `[Workflow]` The `Release PR` workflow validates:
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
11. `[User]` Review and approve the PR.
12. `[Admin]` Merge the PR into `main`.
13. `[Workflow]` After merge, CI creates the tag `v<version>` on the merged commit.

## Rules

- Do not use a manual release workflow on `main`; that flow is obsolete.
- Do not update `CHANGELOG.md` on feature branches unless the user explicitly asks for it.
- Do not open a release PR with extra file changes.
- Do not leave a feature or release branch as multiple commits when the workflow requires one clean commit.
- Do not read or inspect tokens, secrets, or `.env` contents directly.
- Use trusted repo commands that consume credentials implicitly for their normal operation, for example `skiller run pull_request`.
- Do not use ad hoc scripts or generic tooling around credentials when a trusted repo command already exists for the task.
- If a trusted repo command cannot authenticate because the required environment is missing, report that as a blocker.
