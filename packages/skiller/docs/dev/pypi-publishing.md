# PyPI Publishing

## Status and goal

The workflow structure and permission isolation below are implemented locally.
Production deployment still requires verifying environment and Trusted Publisher
settings and exercising the chain against TestPyPI.

After a release PR is merged, create its tag, build once, and publish exactly
those artifacts to PyPI. Keep publication authorization out of the build job.

## Workflows, jobs and permissions

```text
release.yml
├── job: validate — before merge
│   │ Permissions: contents: read
│   ├── Validate release branch and metadata
│   └── Run Ruff, tests and build
│
└── job: create_tag — after merge
    │ Permissions: contents: write, actions: write
    ├── Check out the release merge commit
    ├── Create and push the tag, or verify the existing tag
    └── Dispatch publish.yml on main with the tag

publish.yml
├── job: build
│   │ Permissions: contents: read; no OIDC
│   ├── Validate the tag input
│   ├── Check out the tag without retaining Git credentials
│   ├── Verify tag matches project.version
│   ├── Build wheel and sdist
│   └── Upload distribution artifacts
│
└── job: publish — needs: build
    │ Permissions: id-token: write
    │ Environment: pypi
    ├── Download distribution artifacts from this execution
    ├── Authenticate with PyPI using OIDC
    └── Publish exactly those files
```

Permissions apply to the whole job, not individual steps. Unspecified token
permissions must be disabled. Keep the two jobs in `publish.yml`; no separate
build workflow is needed.

## Release and dispatch

- Preserve existing release PR validation.
- Run tag creation only for a merged `release/*` PR targeting `main`.
- Create `v<version>` on the exact merge commit. On retry, accept an existing tag
  only if it resolves to that commit. Never move or overwrite tags.
- After successful tag creation or verification, dispatch `publish.yml` using
  `GITHUB_TOKEN`, workflow ref `main`, and a single input: `tag`.
- Do not rely on tag-push events: pushes made with `GITHUB_TOKEN` do not normally
  trigger another workflow. Explicit `workflow_dispatch` is supported.
- A successful dispatch means publication was requested, not completed.

## Build and artifact handoff

- Accept automatic and manual `workflow_dispatch` executions only from `main`.
- Require a version tag, not an arbitrary branch or commit input.
- Check out `refs/tags/<tag>` with `persist-credentials: false`.
- Require the tag to equal `v` followed by `project.version`.
- Do not revalidate changelog, PR history, tests or Ruff during publication;
  release PR validation owns those checks.
- Use Python 3.11 to build wheel and sdist once, then upload them as artifacts.
- The publication job downloads only the artifacts produced by the successful
  build job in the same workflow execution. It must not check out source code,
  rebuild the package, or execute project code.
- Fail if expected distribution artifacts are missing.

## Publication security

- Grant `id-token: write` only to the publication job. This allows GitHub to issue
  a short-lived OIDC identity that PyPI verifies through Trusted Publishing.
- Use environment `pypi`; do not introduce a PAT or a persistent PyPI API token.
- Verify that the PyPI Trusted Publisher authorizes the intended repository,
  `publish.yml`, and environment. Restrict the GitHub environment to `main`.
- Pin third-party actions to reviewed full commit SHAs, including the publishing
  action. Review current security advisories when choosing revisions.
- The build job runs project and dependency code without publication authority.
  This separation protects authorization; it does not establish that the built
  package itself is safe.

## Related hardening: GitHub Pages

Apply the same permission isolation to `.github/workflows/pages.yml`. It already
has separate build and deployment jobs. Permissions are now declared per job
instead of inheriting deployment and OIDC permissions at workflow level.

```text
pages.yml
├── job: build
│   │ Permissions: contents: read; no OIDC
│   ├── Check out source without retaining Git credentials
│   ├── Install dependencies, check, build and verify links
│   └── Upload the website artifact outside PR executions
│
└── job: deploy — needs: build; never runs for a PR
    │ Permissions: pages: write, id-token: write
    │ Environment: github-pages
    └── Deploy the website artifact from this execution
```

- Remove workflow-level write permissions; declare permissions per job.
- Preserve PR checks without allowing PR executions to deploy.
- Use `persist-credentials: false` for checkout and pin actions to reviewed SHAs.
- Verify the `github-pages` environment permits deployment only from `main`;
  restrict manual deployment accordingly.
- Add tests proving build has no OIDC or Pages write permission, deployment
  depends on build, and PR executions cannot deploy.

No additional jobs or workflow files are needed. Pages deployment is independent
of the release/tag/PyPI chain.

## Retries and recovery

- Serialize publication by tag with `cancel-in-progress: false`.
- Retry failed dispatch by rerunning the release job; existing-tag verification
  must remain safe.
- Retry publication by dispatching `publish.yml` on `main` with the same tag.
- Concurrency does not prevent sequential duplicate publication. PyPI rejects
  existing files; a retry after successful publication is not automatically a
  successful no-op.
- Do not silently skip existing files, move tags, or bump versions to hide a
  failed upload. Investigate partial uploads before retrying.
- Report failures visibly. On success, report the tag and PyPI version URL.

## Verification and acceptance

- Test release conditions, dispatch inputs, existing-tag retries, invalid tags
  and tag/version mismatches without publishing.
- Verify publication depends on successful build and downloads only this run's
  artifacts.
- Verify OIDC is absent from build and available only in the publication job.
- Verify dispatch from a branch other than `main` cannot publish.
- Exercise the full chain against TestPyPI using a separate environment and
  Trusted Publisher before production use.
- Acceptance: merging a validated release creates its tag and requests automatic
  publication; the published wheel and sdist are the artifacts built from that
  tag, with no long-lived publication credentials.

This specification does not itself authorize creating tags or publishing packages.
Implementation and deployment must follow the repository PR/release procedure.
