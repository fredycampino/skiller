import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[5]


def _workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text())


def _step(workflow, job, name):
    return next(s for s in workflow['jobs'][job]['steps'] if s['name'] == name)


def _run(script, cwd, **env):
    return subprocess.run(
        ['bash', '-c', script], cwd=cwd, env={**os.environ, **env},
        capture_output=True, text=True,
    )


@pytest.mark.parametrize('tag,accepted', [
    ('v0.1.0-beta.46', True),
    ('v1.2.3', True),
    ('main', False),
    ('refs/heads/main', False),
    ('vfoo', False),
    ('v1.2', False),
    ('v1.2.3/extra', False),
])
def test_publication_accepts_only_version_tags(tmp_path, tag, accepted):
    script = _step(_workflow('publish.yml'), 'build', 'Validate tag input')['run']
    result = _run(script, tmp_path, RELEASE_TAG=tag)
    assert (result.returncode == 0) == accepted


@pytest.mark.parametrize('tag', ['v0.1.0-beta.46', 'v0.1.0-beta.45'])
def test_publication_checks_package_version(tmp_path, tag):
    (tmp_path / 'pyproject.toml').write_text('[project]\nversion = "0.1.0-beta.46"\n')
    script = _step(_workflow('publish.yml'), 'build', 'Validate package version')['run']
    result = _run(script, tmp_path, RELEASE_TAG=tag)
    assert (result.returncode == 0) == (tag == 'v0.1.0-beta.46')


def test_tag_creation_retry_and_conflict(tmp_path):
    remote = tmp_path / 'remote.git'
    repo = tmp_path / 'repo'
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    subprocess.run(['git', 'init', str(repo)], check=True, capture_output=True)

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()

    git('config', 'user.name', 'Test')
    git('config', 'user.email', 'test@example.com')
    git('remote', 'add', 'origin', str(remote))
    git('commit', '--allow-empty', '-m', 'release')
    commit = git('rev-parse', 'HEAD')
    script = _step(_workflow('release.yml'), 'create_tag', 'Create or verify release tag')['run']
    env = dict(RELEASE_BRANCH='release/0.1.0-beta.46', MERGE_COMMIT_SHA=commit,
               GITHUB_OUTPUT=str(tmp_path / 'output'))
    assert _run(script, repo, **env).returncode == 0
    assert _run(script, repo, **env).returncode == 0
    assert git('rev-parse', 'refs/tags/v0.1.0-beta.46') == commit
    git('commit', '--allow-empty', '-m', 'another commit')
    env['MERGE_COMMIT_SHA'] = git('rev-parse', 'HEAD')
    assert _run(script, repo, **env).returncode != 0
    assert git('rev-parse', 'refs/tags/v0.1.0-beta.46') == commit


def test_dispatch_follows_successful_tag_step(tmp_path):
    release = _workflow('release.yml')
    steps = release['jobs']['create_tag']['steps']
    assert steps[-2]['id'] == 'tag'
    dispatch = steps[-1]
    assert 'if' not in dispatch
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    gh = bin_dir / 'gh'
    gh.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$ARGUMENTS"\n')
    gh.chmod(0o755)
    arguments = tmp_path / 'arguments'
    result = _run(
        dispatch['run'], tmp_path, PATH=f'{bin_dir}:{os.environ["PATH"]}',
        RELEASE_TAG='v0.1.0-beta.46', GH_REPO='example/demo',
        GITHUB_STEP_SUMMARY=str(tmp_path / 'summary'), ARGUMENTS=str(arguments),
    )
    assert result.returncode == 0
    assert arguments.read_text().splitlines() == [
        'workflow', 'run', 'publish.yml', '--ref', 'main', '--field', 'tag=v0.1.0-beta.46',
    ]
    triggers = _workflow('publish.yml')[True]  # PyYAML interprets the YAML key "on" as True.
    assert set(triggers) == {'workflow_dispatch'}


def test_publication_isolates_build_from_oidc():
    workflow = _workflow('publish.yml')
    assert workflow['permissions'] == {}
    build = workflow['jobs']['build']
    publish = workflow['jobs']['publish']
    assert build['if'] == "github.ref == 'refs/heads/main'"
    assert build['permissions'] == {'contents': 'read'}
    assert publish['permissions'] == {'id-token': 'write'}
    assert publish['needs'] == 'build'
    assert publish['environment'] == 'pypi'
    checkout = _step(workflow, 'build', 'Checkout tagged commit')
    assert checkout['with']['persist-credentials'] is False
    upload = _step(workflow, 'build', 'Upload distribution artifacts')
    download = _step(workflow, 'publish', 'Download distribution artifacts')
    assert upload['with']['name'] == download['with']['name']
    assert upload['with']['if-no-files-found'] == 'error'
    assert set(download['with']) == {'name', 'path'}
    assert not any('checkout@' in step.get('uses', '') for step in publish['steps'])
    assert not any('python -m build' in step.get('run', '') for step in publish['steps'])


@pytest.mark.parametrize('files,success', [
    (['package.whl', 'package.tar.gz'], True),
    (['package.whl'], False),
    (['package.tar.gz'], False),
    ([], False),
])
def test_publication_requires_wheel_and_sdist(tmp_path, files, success):
    distributions = tmp_path / 'dist'
    distributions.mkdir()
    for filename in files:
        (distributions / filename).touch()
    script = _step(_workflow('publish.yml'), 'publish', 'Verify distribution artifacts')['run']
    assert (_run(script, tmp_path).returncode == 0) == success


def test_pages_isolates_build_from_deployment_permissions():
    workflow = _workflow('pages.yml')
    assert workflow['permissions'] == {}
    build = workflow['jobs']['build']
    deploy = workflow['jobs']['deploy']
    assert build['permissions'] == {'contents': 'read'}
    assert deploy['permissions'] == {'pages': 'write', 'id-token': 'write'}
    assert deploy['needs'] == 'build'
    assert deploy['environment']['name'] == 'github-pages'
    assert deploy['if'] == "github.event_name != 'pull_request' && github.ref == 'refs/heads/main'"
    assert _step(workflow, 'build', 'Checkout repository')['with']['persist-credentials'] is False
    for name in ['Configure GitHub Pages', 'Upload website artifact']:
        assert _step(workflow, 'build', name)['if'] == "github.event_name != 'pull_request'"


@pytest.mark.parametrize('name', ['release.yml', 'publish.yml', 'pages.yml'])
def test_workflow_actions_are_pinned_to_commits(name):
    import re

    for job in _workflow(name)['jobs'].values():
        for step in job['steps']:
            if 'uses' in step:
                assert re.fullmatch(r'[\w/-]+@[0-9a-f]{40}', step['uses'])


@pytest.mark.parametrize('action,merged,head,base,validate,create_tag', [
    ('opened', False, 'release/1.2.3', 'main', True, False),
    ('synchronize', False, 'release/1.2.3', 'main', True, False),
    ('reopened', False, 'release/1.2.3', 'main', True, False),
    ('ready_for_review', False, 'release/1.2.3', 'main', True, False),
    ('closed', True, 'release/1.2.3', 'main', False, True),
    ('closed', False, 'release/1.2.3', 'main', False, False),
    ('closed', True, 'feature/1.2.3', 'main', False, False),
    ('opened', False, 'feature/1.2.3', 'main', False, False),
    ('closed', True, 'release-candidate/1.2.3', 'main', False, False),
    ('closed', True, 'release/1.2.3', 'develop', False, False),
    ('opened', False, 'release/1.2.3', 'develop', False, False),
])
def test_release_event_gates_jobs(tmp_path, action, merged, head, base, validate, create_tag):
    workflow = _workflow('release.yml')
    triggers = workflow[True]  # PyYAML interprets the YAML key "on" as True.
    assert set(triggers) == {'pull_request'}
    pull_request = triggers['pull_request']
    assert pull_request['branches'] == ['main']
    triggered = base in pull_request['branches'] and action in pull_request['types']

    for job, expected in [('validate', validate), ('create_tag', create_tag)]:
        # Execute the configured guards, translating the GitHub expression subset
        # used here to Bash. Do not duplicate the guard logic in the test.
        condition = workflow['jobs'][job]['if']
        condition = condition.replace(
            "startsWith(github.event.pull_request.head.ref, 'release/')",
            '"$HEAD_REF" == release/*',
        )
        condition = condition.replace('github.event.action', '"$ACTION"')
        condition = condition.replace('github.event.pull_request.merged', '"$MERGED"')
        result = _run(
            f'[[ {condition} ]]', tmp_path,
            ACTION=action, HEAD_REF=head, MERGED=str(merged).lower(),
        )
        assert result.returncode in (0, 1), result.stderr
        assert (triggered and result.returncode == 0) == expected, job
