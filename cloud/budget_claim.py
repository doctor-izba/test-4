"""Claim an explicitly renewed authorization while retaining prior accounting."""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

repo = os.environ['GITHUB_REPOSITORY']
token = os.environ['GITHUB_TOKEN']
run_id = os.environ['GITHUB_RUN_ID']
path = '.cloud-budget/authorization.json'
url = f'https://api.github.com/repos/{repo}/contents/{path}'
headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
           'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'test-4-budget-guard'}
with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
    existing = json.load(response)
record = json.loads(base64.b64decode(existing['content']))
if record.get('state') != 'authorized' or os.environ.get('GITHUB_RUN_ATTEMPT', '1') != '1':
    raise SystemExit('No unused authorization; reconcile prior cost before another paid run.')
if not 0 < float(record.get('maximum_usd', 0)) <= 3.52:
    raise SystemExit('Unexpected renewed budget; no inference authorized.')
record.update({'state': 'claimed_before_inference', 'run_id': run_id})
body = {'message': f'Claim resumed DeepSeek authorization for run {run_id}', 'sha': existing['sha'],
        'content': base64.b64encode(json.dumps(record, indent=2).encode()).decode()}
request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method='PUT')
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        json.load(response)
except urllib.error.HTTPError as error:
    raise SystemExit(f'Budget claim failed: HTTP {error.code}; no inference authorized.')
print(f'Renewed USD3.52 authorization claimed for run {run_id}; prior cost retained.')
