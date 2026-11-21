#!/usr/bin/env python3
"""Regenerate sample outputs from the engine without changing source data."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from resilience.adapter import Adapter, validate
from resilience.service import Service, BEFORE, AFTER
from resilience.reporting import capture_report, render_report

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    service = Service(Adapter(ROOT / 'data'))
    try:
        for phase, at in [('before', BEFORE), ('after', AFTER)]:
            records = service.rescore(at)
            for record in records: validate(record, service.adapter.schemas['score'])
            write_json(ROOT / 'examples' / f'scores_{phase}.json', records)
        write_json(ROOT / 'examples/ranking_sensitivity.json', service.weight_sensitivity())
        report = capture_report(service, 'AST-0001', ['M-INTAKE2', 'M-SPARES', 'M-STORAGE3'], 'selected')
        (ROOT / 'examples/selected_asset_report.html').write_text(render_report(report), encoding='utf-8')
        write_json(ROOT / 'examples/selected_asset_report_evidence.json', report)
        print('Generated before/after scores, sensitivity and selected-asset report with evidence.')
    finally: service.db.close()

if __name__ == '__main__': main()
