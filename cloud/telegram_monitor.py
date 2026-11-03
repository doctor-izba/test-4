"""Read-only Actions monitor; outbound Telegram updates require no server/webhook."""
import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


def status_text(run, jobs, detail=None):
    active = [step['name'] for job in jobs for step in job.get('steps', []) if step.get('status') == 'in_progress']
    failed = [step['name'] for job in jobs for step in job.get('steps', []) if step.get('conclusion') == 'failure']
    lines = ['test-4 / облачная команда DeepSeek',
             'Состояние: ' + (run.get('conclusion') or run.get('status') or 'unknown')]
    if active:
        lines.append('Этап: ' + '; '.join(active))
    if failed:
        lines.append('Ошибка шага: ' + '; '.join(failed))
    if detail:
        usage, summary = detail
        if usage:
            lines.append('API: $' + str(usage.get('confirmed_usd', '?')) + ' подтверждено; $' + str(usage.get('reserved_usd', '?')) + ' зарезервировано')
        if summary:
            lines.extend(role + ': ' + result.get('state', '?') for role, result in summary.get('roles', {}).items())
    lines.extend(['Подробный лог: ' + run.get('html_url', ''),
                  'Репозиторий: https://github.com/doctor-izba/test-4'])
    return '\n'.join(lines)[:4000]


class Monitor:
    def __init__(self, repo, run_id, tg_token, chat_id, gh_token):
        self.repo, self.run_id = repo, str(run_id)
        self.tg_token, self.chat_id, self.gh_token = tg_token, chat_id, gh_token

    def github(self, path):
        request = urllib.request.Request('https://api.github.com/repos/' + self.repo + '/' + path,
            headers={'Authorization': 'Bearer ' + self.gh_token, 'Accept': 'application/vnd.github+json', 'User-Agent': 'test-4-monitor'})
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)

    def telegram(self, method, payload):
        body = json.dumps({'chat_id': self.chat_id, **payload}).encode()
        request = urllib.request.Request('https://api.telegram.org/bot' + self.tg_token + '/' + method,
            data=body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.load(response)
        if not data.get('ok'):
            raise RuntimeError('Telegram returned non-ok response')
        return data['result']

    def final_detail(self):
        result = []
        for name in ['usage.json', 'run-summary.json']:
            try:
                data = self.github('contents/public-evidence/run/' + name + '?ref=' + urllib.parse.quote('results/run-' + self.run_id, safe=''))
                result.append(json.loads(base64.b64decode(data['content'])))
            except (urllib.error.HTTPError, KeyError, ValueError):
                result.append(None)
        return tuple(result)

    def run(self, minutes=220, interval=30):
        deadline = time.monotonic() + minutes * 60
        previous = None
        message_id = None
        while time.monotonic() < deadline:
            try:
                run = self.github('actions/runs/' + self.run_id)
                jobs = self.github('actions/runs/' + self.run_id + '/jobs').get('jobs', [])
                done = run.get('status') == 'completed'
                text = status_text(run, jobs, self.final_detail() if done else None)
                if text != previous:
                    if message_id is None:
                        message_id = self.telegram('sendMessage', {'text': text, 'disable_web_page_preview': True})['message_id']
                    else:
                        self.telegram('editMessageText', {'message_id': message_id, 'text': text, 'disable_web_page_preview': True})
                    previous = text
                    print('Updated Telegram status; no credentials or recipient IDs logged.', flush=True)
                if done:
                    return 0
            except Exception as error:
                # Exception URLs may contain the bot token; only log its type/code.
                print('Monitor request failed:', type(error).__name__, getattr(error, 'code', ''), flush=True)
            time.sleep(interval)
        print('Monitor deadline reached; this does not cancel the research workflow.', flush=True)
        return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True, type=int)
    args = parser.parse_args()
    required = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'GITHUB_TOKEN', 'GITHUB_REPOSITORY']
    if not all(os.environ.get(name) for name in required):
        raise SystemExit('Missing monitor configuration; no messages sent.')
    raise SystemExit(Monitor(os.environ['GITHUB_REPOSITORY'], args.run_id,
        os.environ['TELEGRAM_BOT_TOKEN'], os.environ['TELEGRAM_CHAT_ID'], os.environ['GITHUB_TOKEN']).run())
