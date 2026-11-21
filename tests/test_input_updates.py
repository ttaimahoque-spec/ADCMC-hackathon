"""Dated inputs, change attribution, adapter boundary and daily runs."""
import copy
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from unittest.mock import patch
from resilience.adapter import Adapter, ROOT, canonical, validate
from resilience.engine import input_change_candidates, pillars, score_value, warning_state
from resilience.reporting import capture_report, render_report
from resilience.service import Service, BEFORE, AFTER
from run import make_handler
UPDATE_AT = '2026-08-28T06:40:00+04:00'

class InputUpdateTests(unittest.TestCase):
    def setUp(self): self.service = Service(Adapter(ROOT / 'data'), replay=False)
    def tearDown(self): self.service.db.close()
    def facility(self): return copy.deepcopy(self.service.adapter.by_id['AST-0001'])
    def update(self, f, at=UPDATE_AT): return self.service.ingest_inputs({'effective_at': at, 'facilities': [f]})

    def test_audit_control_and_recovery_are_individual_counterfactuals(self):
        old = self.facility(); updated = copy.deepcopy(old)
        updated['audit_domains'][0]['score'] = 10
        updated['controls'][0]['state'] = 'absent'
        updated['continuity']['buffer_hours'] = 0
        self.update(updated)
        record = self.service.records['AST-0001']; changes = {c['factor']: c for c in record['input_changes']}
        a = self.service.adapter
        value = lambda f: score_value(pillars(f, a.exposure_index['AST-0001'], warning_state(a.warnings, UPDATE_AT), a.city['population']))
        counterfactuals = []
        v = copy.deepcopy(updated); v['audit_domains'][0]['score'] = old['audit_domains'][0]['score']; counterfactuals.append(('Audit: physical_condition / score changed', v))
        v = copy.deepcopy(updated); v['controls'][0]['state'] = old['controls'][0]['state']; counterfactuals.append(('Control: intake screening / state changed', v))
        v = copy.deepcopy(updated); v['continuity']['buffer_hours'] = old['continuity']['buffer_hours']; counterfactuals.append(('Continuity: buffer hours changed', v))
        for name, f in counterfactuals:
            self.assertEqual(changes[name]['effect'], round(value(updated) - value(f), 1))
            self.assertGreater(changes[name]['effect'], 0)
        self.assertEqual(self.service.source_adapter.by_id['AST-0001'], old)
        validate(record, a.schemas['score'])

    def test_improvements_have_negative_effects_and_can_be_top_drivers(self):
        f = self.facility()
        for audit in f['audit_domains']: audit['score'] = 0
        for control in f['controls']: control['state'] = 'tested_current'
        f['continuity'].update(n1_redundant=True, buffer_hours=72, rto_hours=24,
                               spares_on_site=True, plan_current=True, exercise='full')
        self.update(f); r = self.service.records['AST-0001']
        self.assertTrue(any(c['kind'] == 'change' and c['effect'] < 0 for c in r['drivers']))
        self.assertLess(r['score'], 71)

    def test_reordering_is_not_a_change_and_removals_restore_membership(self):
        f = self.facility(); f['audit_domains'].reverse(); f['controls'].reverse()
        self.update(f); self.assertEqual(self.service.records['AST-0001']['input_changes'], [])
        old = copy.deepcopy(f); f['controls'].pop()
        a = self.service.adapter
        changes = input_change_candidates(f, a.exposure_index['AST-0001'], warning_state(a.warnings, UPDATE_AT), 1000000,
            {'facility': old, 'exposures': a.exposure_index['AST-0001'], 'population': 1000000})
        self.assertEqual(len(changes), 1); self.assertIsNone(changes[0]['current']); self.assertIsInstance(changes[0]['previous'], dict)

    def test_metadata_is_recorded_with_zero_risk_effect(self):
        f = self.facility(); f['controls'][0]['verified_at'] = None; self.update(f)
        r = self.service.records['AST-0001']; change = next(c for c in r['input_changes'] if 'verified_at' in c['factor'])
        self.assertEqual(change['effect'], 0); self.assertEqual(r['score'], 71)
        self.assertNotIn(change['factor'], [d['factor'] for d in r['drivers']])

    def test_exposure_population_and_consequence_are_attributed(self):
        f = self.facility(); f['category'] = 5; f['people_served'] = 900000; f['share_of_city_supply'] = .1
        exp = copy.deepcopy(next(e for e in self.service.adapter.exposure_index['AST-0001'] if e['channel_id'] == 2)); exp['exposed'] = False
        self.service.ingest_inputs({'effective_at': UPDATE_AT, 'facilities': [f], 'exposures': [exp], 'population': 2000000})
        changes = {c['factor']: c['effect'] for c in self.service.records['AST-0001']['input_changes']}
        for name in ['Exposure: channel 2 changed', 'City population changed', 'Facility: category changed']: self.assertLess(changes[name], 0)
        self.assertGreater(changes['Facility: people served changed'], 0)

    def test_replay_and_reports_exclude_future_inputs(self):
        f = self.facility(); f['continuity']['spares_on_site'] = True; self.update(f)
        self.assertTrue(self.service.adapter.by_id['AST-0001']['continuity']['spares_on_site'])
        self.service.rescore(AFTER); report = capture_report(self.service)
        self.assertFalse(self.service.adapter.by_id['AST-0001']['continuity']['spares_on_site'])
        self.assertEqual(self.service.records['AST-0001']['score'], 71)
        self.assertFalse(report['input_updates']); self.assertFalse(report['dashboard']['events'])
        self.service.rescore(UPDATE_AT)
        self.assertEqual(self.service.records['AST-0001']['score_exact'], 66.2)
        self.assertEqual(len(capture_report(self.service)['input_updates']), 1)
        self.assertIn('Recorded source-input changes', render_report(capture_report(self.service)))

    def test_comparison_uses_previous_day_not_previous_import(self):
        f = self.facility(); f['continuity']['spares_on_site'] = True; self.update(f)
        f['continuity']['buffer_hours'] = 72; self.update(f, '2026-08-28T07:00:00+04:00')
        factors = [c['factor'] for c in self.service.records['AST-0001']['input_changes']]
        self.assertIn('Continuity: spares on site changed', factors); self.assertIn('Continuity: buffer hours changed', factors)
        self.service.rescore('2026-08-29T07:00:00+04:00')
        self.assertEqual(self.service.records['AST-0001']['input_changes'], [])

    def test_updates_are_duplicate_safe_and_survive_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            db = str(Path(temp) / 'history.sqlite3'); service = Service(Adapter(ROOT / 'data'), db, replay=False)
            f = copy.deepcopy(service.adapter.by_id['AST-0001']); f['continuity']['spares_on_site'] = True
            payload = {'effective_at': UPDATE_AT, 'facilities': [f]}
            self.assertEqual(service.ingest_inputs(payload)['versions'], 1)
            record = copy.deepcopy(service.records['AST-0001']); count = service.db.execute('SELECT COUNT(*) FROM scores').fetchone()[0]
            self.assertEqual(service.ingest_inputs(payload)['versions'], 0)
            self.assertEqual(service.db.execute('SELECT COUNT(*) FROM scores').fetchone()[0], count)
            service.db.close(); restored = Service(Adapter(ROOT / 'data'), db, at=UPDATE_AT, replay=False)
            try:
                self.assertEqual(restored.records['AST-0001'], record)
                self.assertEqual(restored.events[-1]['kind'], 'input_import')
            finally: restored.db.close()

    def test_rejections_and_scoring_failure_leave_stores_unchanged(self):
        baseline = canonical(self.service.dashboard()); f = self.facility()
        bad = [[], {}, {'effective_at': UPDATE_AT, 'population': 0}, {'effective_at': UPDATE_AT, 'population': True},
               {'effective_at': '2026-08-28', 'population': 10}, {'effective_at': BEFORE, 'facilities': [f]},
               {'effective_at': UPDATE_AT, 'facilities': [f, f]}, {'effective_at': UPDATE_AT, 'measures': []}]
        for payload in bad:
            with self.subTest(payload=payload):
                with self.assertRaises((ValueError, TypeError)): self.service.ingest_inputs(payload)
                self.assertEqual(canonical(self.service.dashboard()), baseline)
                self.assertEqual(self.service.db.execute('SELECT COUNT(*) FROM input_updates').fetchone()[0], 0)
        with patch('resilience.service.score_record', side_effect=ValueError('simulation failure')):
            with self.assertRaisesRegex(ValueError, 'simulation failure'): self.update(f)
        self.assertEqual(canonical(self.service.dashboard()), baseline)

    def test_daily_run_once_at_day_boundary(self):
        before = self.service.db.execute('SELECT COUNT(*) FROM scores').fetchone()[0]
        self.assertEqual(self.service.daily_tick('2026-08-27T23:59:59+04:00'), [])
        self.assertEqual(len(self.service.daily_tick('2026-08-28T00:00:01+04:00')), 60)
        self.assertEqual(self.service.db.execute('SELECT COUNT(*) FROM scores').fetchone()[0], before + 60)
        self.assertEqual(self.service.daily_tick('2026-08-28T00:00:31+04:00'), [])
        self.assertEqual(self.service.daily_tick('2026-08-26T00:00:00+04:00'), [])

    def test_optional_subassets_validate_and_report_uses_loaded_adapter(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'data'; shutil.copytree(ROOT / 'data', source); adapter = Adapter(source)
            service = Service(adapter, replay=False)
            try:
                (source / 'sub_assets.json').write_text('invalid after load')
                self.assertEqual(capture_report(service)['sub_assets'], adapter.sub_assets)
            finally: service.db.close()
            with self.assertRaises(ValueError): Adapter(source)
            (source / 'sub_assets.json').unlink(); self.assertEqual(Adapter(source).sub_assets, [])
            parts = copy.deepcopy(adapter.sub_assets); parts[0]['asset_id'] = 'AST-9999'
            (source / 'sub_assets.json').write_text(json.dumps(parts))
            with self.assertRaisesRegex(ValueError, 'unknown'): Adapter(source)

    def test_input_http_template_and_import(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start(); base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base + '/api/input-template?asset=AST-0001') as response: payload = json.load(response)
            self.assertNotIn('result', payload['facilities'][0]); payload['effective_at'] = UPDATE_AT
            payload['facilities'][0]['continuity']['spares_on_site'] = True
            request = Request(base + '/api/inputs', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            with urlopen(request) as response: self.assertEqual(json.load(response)['versions'], 1)
            self.assertEqual(self.service.records['AST-0001']['score_exact'], 66.2)
        finally: server.shutdown(); server.server_close(); thread.join()

if __name__ == '__main__': unittest.main()
