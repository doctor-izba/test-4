"""Local-only checker using another project's already downloaded mathlib cache.

Pass the dependency project directory explicitly. It does not edit that project.
This helper is not needed in cloud, where lake build runs in this directory.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('dependency_project', type=Path)
args = parser.parse_args()
here = Path(__file__).resolve().parent
source = here / 'Assignment4Verification.lean'
audit = here / 'AxiomAudit.lean'
combined = source.read_text(encoding='utf-8') + '\n' + '\n'.join(
    line for line in audit.read_text(encoding='utf-8').splitlines() if line.startswith('#print axioms ')) + '\n'
started = time.time()
with tempfile.TemporaryDirectory(prefix='robotics-lean-audit-') as temporary:
    target = Path(temporary) / 'CombinedAudit.lean'
    target.write_text(combined, encoding='utf-8')
    result = subprocess.run(['rtk', 'proxy', 'lake', 'env', 'lean', str(target)],
                            cwd=args.dependency_project.resolve(), capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=900)
    log = result.stdout + result.stderr
    # Logs retain diagnostics and axioms; strip machine-specific source prefixes.
    log = log.replace(str(target), 'CombinedAudit.lean')
    (here / 'local-build.log').write_text(log, encoding='utf-8')
    status = {'command': 'lake env lean CombinedAudit.lean',
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'audit_sha256': hashlib.sha256(audit.read_bytes()).hexdigest(),
              'exit_code': result.returncode, 'elapsed_seconds': round(time.time()-started, 2),
              'audit_theorem_count': sum(x.startswith('#print axioms ') for x in audit.read_text(encoding='utf-8').splitlines()),
              'scope': 'Source+axioms compilation using existing dependencies; not a clean pinned cloud build.'}
    (here / 'local-verification.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    print(log, end='')
    print(json.dumps(status, indent=2))
    raise SystemExit(result.returncode)
