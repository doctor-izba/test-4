"""Allowlist original authored outputs; exclude raw sourcebooks and API histories."""
from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parent.parent
target = root / 'public-evidence'
target.mkdir(exist_ok=True)
allowed = {'.md', '.json', '.csv', '.svg', '.png', '.pdf', '.lean', '.toml', '.log', '.py', '.m'}
manifest = []
for directory in ['lean', 'simulation', 'review', 'reports', 'research/notes']:
    source = root / directory
    if not source.exists():
        continue
    for path in source.rglob('*'):
        relative = path.relative_to(root)
        if path.is_symlink() or not path.is_file() or any(part in ['.lake', '.home', '__pycache__', 'raw', '.git'] for part in relative.parts):
            continue
        if path.suffix.lower() not in allowed or path.stat().st_size > 8_000_000:
            continue
        if path.suffix.lower() == '.pdf' and directory != 'reports':
            continue
        output = target / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, output)
        manifest.append({'path': relative.as_posix(), 'bytes': path.stat().st_size,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
for name in ['usage.json', 'status.json', 'run-summary.json', 'research-result.json', 'lean-result.json', 'simulation-result.json', 'reviewer-result.json', 'writer-result.json']:
    path = root / 'output' / name
    if path.exists() and path.is_file() and not path.is_symlink():
        destination = target / 'run' / name
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(path, destination)
(target / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(f'Collected {len(manifest)} authored/evidence files; raw research downloads and request histories excluded.')
