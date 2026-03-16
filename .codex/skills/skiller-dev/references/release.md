# Release Procedure

Use this repo flow unless the user says otherwise:

1. After the pull request is merged into `main`, a human runs the `Release` GitHub Actions workflow.
2. The workflow receives the target version, for example `1.0.0-alpha.4`.
3. The workflow validates:
   - `ruff`
   - `pytest`
   - package build
   - `CHANGELOG.md`
   - `project.version` in `pyproject.toml` matches the requested version
4. If validation passes, the workflow creates the version tag `v<version>`.
5. GitHub Release creation and PyPI publication are outside this first cut.
