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

Run MiniMax setup through the generic OpenAI-compatible auth flow:

```bash
scripts/qa/android-sim/run.sh skiller run auths/openai --arg provider=minimax --logs
```

Use Podman or another Docker-compatible CLI:

```bash
SKILLER_CONTAINER_ENGINE=podman scripts/qa/android-sim/run.sh skiller run auths/openai --arg provider=minimax --logs
```

Historical failure reproduced with the older package versions above:

```text
python3: can't open file '/home/droid/packages/skiller/agents/auths/minimax_auth.py'
```

When testing a version with the generic OpenAI-compatible auth flow, setup should
reach the `ask_api_key` waiting step instead. Older package versions may only
provide the former `auths/minimax` flow.
