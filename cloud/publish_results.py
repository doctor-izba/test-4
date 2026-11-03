"""Trusted publisher: only allowlisted evidence, separate branch, no token logging."""
from pathlib import Path
import os
import subprocess

root = Path(__file__).resolve().parent.parent
run = os.environ['GITHUB_RUN_ID']
repo = os.environ['GITHUB_REPOSITORY']
token = os.environ['GITHUB_TOKEN']

def git(*args):
    subprocess.run(['git', *args], cwd=root, check=True)

git('config', 'user.name', 'test-4 cloud results')
git('config', 'user.email', 'actions@users.noreply.github.com')
git('checkout', '-b', 'results/run-' + run)
git('add', '--', 'public-evidence')
changes = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=root)
if changes.returncode == 0:
    print('No generated evidence to publish.')
    raise SystemExit(0)
git('commit', '-m', f'Publish measured cloud evidence for run {run}')
# Credential travels through child env and credential helper stdin, never argv/URL.
environment = os.environ.copy()
environment['GIT_CONFIG_COUNT'] = '2'
environment['GIT_CONFIG_KEY_0'] = 'credential.helper'
environment['GIT_CONFIG_VALUE_0'] = ''
environment['GIT_CONFIG_KEY_1'] = 'credential.helper'
environment['GIT_CONFIG_VALUE_1'] = '!f() { echo username=x-access-token; echo "password=$GITHUB_TOKEN"; }; f'
subprocess.run(['git', 'push', f'https://github.com/{repo}.git', 'HEAD'], cwd=root, env=environment, check=True)
print(f'Published evidence branch results/run-{run}.')
