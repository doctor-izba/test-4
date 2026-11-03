"""Trusted job supervisor: restart crashes and keep independent cloud checkpoints."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import ctypes
import json
import os
import subprocess
import sys
import time

root = Path(__file__).resolve().parent.parent
output = root / 'output'
output.mkdir(exist_ok=True)
try:
    ctypes.CDLL(None).prctl(4, 0, 0, 0, 0)
except Exception:
    pass
started = datetime.fromisoformat(os.environ['TEAM_STARTED_UTC'])
deadline = started + timedelta(minutes=355)
broker_env = {key: value for key, value in os.environ.items() if key != 'NUBE_API_KEY'}
worker_env = {key: value for key, value in os.environ.items()
              if not any(part in key.upper() for part in ['GITHUB_TOKEN', 'GH_TOKEN', 'TELEGRAM_', 'ACTIONS_RUNTIME_TOKEN'])}
broker = subprocess.Popen([sys.executable, 'cloud/checkpoint_publisher.py'], cwd=root, env=broker_env)
authorization = json.loads((root / '.cloud-budget/authorization.json').read_text(encoding='utf-8'))
remaining_budget = str(authorization['maximum_usd'])
command = [sys.executable, 'harness/run.py', '--root', '.', '--budget', remaining_budget,
           '--deadline-utc', deadline.isoformat(), '--steps', '0', '--slice-rounds', '12',
           '--max-output-tokens', '393216', '--reasoning', 'max', '--retries', '5',
           '--work-until-deadline']
code = 1
try:
    attempt = 0
    while datetime.now(timezone.utc) < deadline:
        attempt += 1
        if datetime.now(timezone.utc) >= deadline:
            break
        print(f'Supervisor: process attempt {attempt}; sessions and monetary ledger preserved.', flush=True)
        process = subprocess.Popen(command, cwd=root, env=worker_env, start_new_session=True)
        while process.poll() is None:
            if datetime.now(timezone.utc) >= deadline:
                print('Supervisor: GitHub cleanup window reached; requesting final checkpoint.', flush=True)
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                break
            time.sleep(5)
        code = process.wait()
        if code == 0:
            break
        try:
            usage = json.loads((output / 'usage.json').read_text())
        except (FileNotFoundError, ValueError):
            usage = {}
        if usage.get('stop_reason'):
            print('Supervisor: accounting/auth stop requires reconciliation; no blind restart.', flush=True)
            break
        if datetime.now(timezone.utc) >= deadline or (output / 'STOP').exists():
            break
        print('Supervisor: restarting saved sessions; uncertain request costs stay reserved and unknown tools are not replayed.', flush=True)
        time.sleep(min(120, 5 * attempt))
finally:
    (output / 'publisher.stop').write_text('final checkpoint requested', encoding='utf-8')
    try:
        broker.wait(timeout=45)
    except subprocess.TimeoutExpired:
        broker.terminate()
        print('Publisher shutdown timeout; earlier cloud checkpoints remain.', flush=True)
raise SystemExit(code)
