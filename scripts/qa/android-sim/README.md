# Android-like Debian Simulation

This Docker fixture reproduces the important runtime conditions from an installed
Android terminal environment:

- Skiller is installed from PyPI as a package.
- The current user is `droid`.
- `HOME` and `cwd` are `/home/droid`.
- There is no repo checkout at `/home/droid/packages/skiller`.

By default the image installs `skiller==0.1.0-beta.4`. Override the package spec
when testing another published version:

```bash
SKILLER_PACKAGE=skiller==0.1.0-beta.5 scripts/qa/android-sim/run.sh
```

Build and open a shell:

```bash
scripts/qa/android-sim/run.sh
```

Run the MiniMax auth flow directly:

```bash
scripts/qa/android-sim/run.sh skiller run auths/minimax --logs
```

Use Podman or another Docker-compatible CLI:

```bash
SKILLER_CONTAINER_ENGINE=podman scripts/qa/android-sim/run.sh skiller run auths/minimax --logs
```

The current failure mode is:

```text
python3: can't open file '/home/droid/packages/skiller/agents/auths/minimax_auth.py'
```

After the auth helper path is fixed, the MiniMax auth flow should reach the
`ask_api_key` waiting step instead.
