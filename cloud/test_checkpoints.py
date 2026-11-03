"""Offline test of checkpoint contents and deduplication; no network or tokens."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class CheckpointTests(unittest.TestCase):
    def test_snapshot_excludes_secrets_cache_books_and_deduplicates(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'fixture/repo', 'GITHUB_RUN_ID': '1',
                                     'GITHUB_TOKEN': 'offline-fixture'}, clear=False):
            spec = importlib.util.spec_from_file_location('fixture_broker', Path(__file__).with_name('checkpoint_publisher.py'))
            broker = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(broker)
        with tempfile.TemporaryDirectory() as directory:
            broker.ROOT = Path(directory)
            fixture = {'lean/A.lean': 'theorem sample : True := True.intro',
                       'lean/lean-toolchain': 'leanprover/lean4:v4.34.0',
                       'lean/.lake/private.json': 'excluded',
                       'research/raw/book.pdf': 'excluded',
                       'research/notes/decision.md': 'original note',
                       'output/usage.json': '{"confirmed_usd":"0"}',
                       'output/secret.json': 'excluded', '.env': 'excluded'}
            for name, content in fixture.items():
                path = broker.ROOT / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')
            calls = []
            def fake_api(path, payload=None, method=None):
                calls.append((path, payload))
                if path.startswith('git/ref/'):
                    return {'object': {'sha': 'head'}}
                if path.startswith('git/commits/'):
                    return {'tree': {'sha': 'base-tree'}}
                return {'sha': 'fixture-' + str(len(calls))}
            broker.api = fake_api
            with patch.object(broker.time, 'sleep'):
                broker.snapshot()
            tree = next(payload for path, payload in calls if path == 'git/trees')
            names = {entry['path'] for entry in tree['tree']}
            self.assertEqual(names, {'checkpoint/lean/A.lean', 'checkpoint/lean/lean-toolchain',
                                     'checkpoint/research/notes/decision.md', 'checkpoint/run/usage.json'})
            count = len(calls)
            broker.snapshot()
            self.assertEqual(len(calls), count, 'Unchanged snapshot should not create another commit')


if __name__ == '__main__':
    unittest.main()
