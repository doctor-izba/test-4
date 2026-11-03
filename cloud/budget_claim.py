"""One-shot repository authorization, independent of the model/tool process."""
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
try:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        existing = json.load(response)
except urllib.error.HTTPError as error:
    if error.code != 404:
        raise SystemExit(f'Budget lookup failed: HTTP {error.code}; no inference authorized.')
    existing = None
if existing is not None:
    raise SystemExit('One-shot authorization already claimed. No further paid run is authorized.')
if os.environ.get('GITHUB_RUN_ATTEMPT', '1') != '1':
    raise SystemExit('Rerun blocked; inspect previous accounting before any new authorization.')
record = {'state': 'claimed_before_inference', 'run_id': run_id, 'maximum_usd': 3.70,
          'note': 'This authorization cannot be automatically reused, even if a run fails.'}
body = {'message': f'Reserve single DeepSeek budget for run {run_id}',
        'content': base64.b64encode(json.dumps(record, indent=2).encode()).decode()}
request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method='PUT')
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        json.load(response)
except urllib.error.HTTPError as error:
    raise SystemExit(f'Budget claim failed: HTTP {error.code}; no inference authorized.')
print(f'One-shot USD3.70 budget claimed for run {run_id}; repeat paid runs blocked.')
