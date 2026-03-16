# Pre-Release Procedure

Use this repo flow unless the user says otherwise:

1. The human creates a branch from `main` named `feature/<topic>`.
2. The agent works on that branch, makes the required code changes, verifies them, and commits freely while the feature is in progress.
3. When the branch is considered release-ready, the agent updates `CHANGELOG.md` with a short functional summary of the branch.
4. The human reviews the changelog and confirms the branch is ready to go out.
5. The agent squashes the branch into one clean commit on top of `main` and verifies the branch compares cleanly against `main`.
6. The human opens the pull request.
7. The admin merges the pull request into `main`.
