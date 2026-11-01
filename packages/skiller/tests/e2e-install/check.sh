#!/usr/bin/env bash
set -euo pipefail

# Run only inside the disposable image, never against the host home.
[[ "$HOME" == /home/tester ]]
[[ ! -e "$HOME/.skiller" ]]
[[ ! -v SKILLER_DB_PATH ]]
[[ ! -v SKILLER_RUNTIME_CONFIG_FILE ]]
mkdir -p "$HOME/workspace/a" "$HOME/workspace/b"
cd "$HOME/workspace/a"

: "${SKILLER_MINIMAX_API_KEY:?Missing injected MiniMax credential}"
mkdir -p "$HOME/.skiller/settings"
cat > "$HOME/.skiller/settings/agent.json" <<'JSON'
{"llm": {"provider": "minimax", "model": "MiniMax-M3.1-Flash"}}
JSON
cat > "$HOME/.skiller/settings/providers.json" <<'JSON'
{"providers": {"minimax": {"api_key_env": "SKILLER_MINIMAX_API_KEY"}}}
JSON

# First installed-CLI launch initializes Runtime, not the test setup.
skiller run @flows > /tmp/first-run.json
python3 - <<'PY'
import json
from pathlib import Path
home = Path.home()
config = json.loads((home / '.skiller/settings/config.json').read_text())
assert config['runtime']['db_path'] == '~/.skiller/runtime/global.db'
assert (home / '.skiller/runtime/global.db').is_file()
assert (home / '.skiller/settings/agent.flows.json').is_file()
assert (home / '.skiller/settings/agent.json').is_file(), 'Missing agent configuration'
PY

# Keep the assertions on the installed CLI, not on repository imports.
run_id="$(python3 -c 'import json; print(json.load(open("/tmp/first-run.json"))["run_id"])')"
python3 -c 'import json; assert json.load(open("/tmp/first-run.json"))["status"] == "WAITING"'
skiller input receive "$run_id" --text 'Reply with exactly FIRST_INSTALL_OK. Do not call tools.' --wait > /tmp/task.json
skiller status "$run_id" > /tmp/task-status.json
skiller logs "$run_id" > /tmp/task-logs.json
python3 - <<'PY'
import json
logs = json.load(open('/tmp/task-logs.json'))
answers = [e['payload']['text'] for e in logs if e['type'] == 'AGENT_FINAL_ASSISTANT_MESSAGE']
assert answers and answers[-1].strip() == 'FIRST_INSTALL_OK', answers
assert json.load(open('/tmp/task-status.json'))['status'] == 'WAITING'
PY

python3 - <<'PY'
import json
from pathlib import Path
home = Path.home()
profile = home / '.skiller/settings/agent.flows.json'
database = home / '.skiller/runtime/global.db'
Path('/tmp/initial-files.json').write_text(json.dumps({
    'profile': profile.read_text(),
    'profile_inode': profile.stat().st_ino,
    'database_inode': database.stat().st_ino,
}))
PY

cd "$HOME/workspace/b"
skiller run @flows > /tmp/second-run.json
skiller status "$run_id" > /tmp/previous-status.json
python3 - <<'PY'
import json
from pathlib import Path
home = Path.home()
snapshot = json.load(open('/tmp/initial-files.json'))
profile = home / '.skiller/settings/agent.flows.json'
database = home / '.skiller/runtime/global.db'
assert profile.read_text() == snapshot['profile']
assert profile.stat().st_ino == snapshot['profile_inode']
assert database.stat().st_ino == snapshot['database_inode']
assert json.load(open('/tmp/second-run.json'))['status'] == 'WAITING'
assert json.load(open('/tmp/previous-status.json'))['status'] == 'WAITING'
assert list(home.rglob('*.db')) == [database], 'Unexpected additional database'
assert not (home / 'workspace/a/runtime.db').exists()
assert not (home / 'workspace/b/runtime.db').exists()
print('PASS: Flows answered; both directories share one database and the same profile.')
PY

printf '\nPASS: automated first-install E2E with a real MiniMax response.\n'
