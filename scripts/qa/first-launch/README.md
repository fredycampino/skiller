# First-launch QA environment

A disposable Ubuntu 26.04 user environment with the current local Skiller wheel
already installed using pipx. This is a manual QA tool, not an automated test.
Requires Docker and `uv` on the host, plus internet access to build the image.

From the repository root:

```bash
bash scripts/qa/first-launch/qa.sh build
bash scripts/qa/first-launch/qa.sh start
```

`start` opens Bash as the non-root user `tester`. The first time, the home has
no Skiller configuration, credentials, database or STUI session. No host home,
repository, environment credentials or Docker socket are mounted or injected.
Run commands freely, as a new user who has just installed Skiller with pipx:

```bash
skiller --version
pipx list
skiller
```

Closing STUI returns to Bash. `exit` leaves the container running and retains
all files and background processes. Run `start` again to re-enter the same
environment; the shell starts in `/home/tester` each time. A stopped container
is restarted automatically. Multiple terminals can enter the same environment.

To delete the environment and reproduce a new installation:

```bash
bash scripts/qa/first-launch/qa.sh reset
bash scripts/qa/first-launch/qa.sh start
```

**Reset permanently deletes all QA data and credentials in the container.**
It only removes the named container carrying this tool's ownership label.
The image remains available. No host files are deleted.

After changing the code, run `build`, then `reset` and `start`: rebuilding the
image does not update an existing container. The image contains the installed
wheel, not editable repository sources. Nothing launches Skiller during build
or container startup, so the first launch is yours to perform.

The container has outbound network access but publishes no ports. Authentication
and model calls are real and may incur costs. Any credentials entered during QA
remain in the container until reset; do not share or export its filesystem.
Browser-based OAuth callbacks on the host are not forwarded into this container.
This environment is not a security sandbox for untrusted agents or commands.
