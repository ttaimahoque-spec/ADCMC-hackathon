#!/usr/bin/env python3
"""One-command preflight; optional --browser requires Playwright + Chromium."""
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--browser', action='store_true')
args = parser.parse_args()
checks = [[sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
          [sys.executable, 'scripts/verify_offline.py']]
if shutil.which('node'):
    checks.append(['node', '--test', 'tests/test_visuals.js', 'tests/test_asset3d.js', 'tests/test_report_actions.js'])
if args.browser: checks.append([sys.executable, '-m', 'tests.browser_smoke'])
result = {'at': datetime.now(timezone.utc).isoformat(), 'checks': [],
          'browser': 'requested' if args.browser else 'not run; rehearse in your browser',
          'node': 'available' if shutil.which('node') else 'not installed; optional JavaScript checks skipped'}
for command in checks:
    print('Running: ' + ' '.join(command), flush=True)
    process = subprocess.run(command, cwd=ROOT, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(process.stdout, flush=True)
    result['checks'].append({'command': command, 'exit_code': process.returncode, 'output': process.stdout})
    if process.returncode: break
folder = ROOT / 'var'; folder.mkdir(exist_ok=True)
(folder / 'submission-checks.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
failed = any(c['exit_code'] for c in result['checks'])
print('Checks failed. See var/submission-checks.json.' if failed else 'Requested checks passed. See var/submission-checks.json.')
sys.exit(1 if failed else 0)
