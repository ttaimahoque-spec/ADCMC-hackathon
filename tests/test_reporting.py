"""Report correctness, frozen snapshots, privacy of future data and safe HTML."""
import copy
import hashlib
import json
import threading
import unittest
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen
from resilience.adapter import Adapter, ROOT, canonical
from resilience.reporting import capture_report, render_report, report_script
from resilience.service import Service, BEFORE, AFTER
from run import make_handler


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.payload = ''; self.in_payload = False
        self.scripts = []; self.external = []; self.ids = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag == 'script':
            self.scripts.append(attrs)
            self.in_payload = attrs.get('id') == 'report-data'
        if tag in ('script', 'link', 'img', 'iframe') and (attrs.get('src') or attrs.get('href')):
            self.external.append(attrs)
    def handle_endtag(self, tag):
        if tag == 'script': self.in_payload = False
    def handle_data(self, data):
        if self.in_payload: self.payload += data


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.service = Service(Adapter(ROOT / 'data'), replay=False)
    def tearDown(self):
        self.service.db.close()

    def test_complete_report_is_frozen_and_does_not_mutate_baseline(self):
        service = self.service
        before = copy.deepcopy(service.records)
        rows_before = service.db.execute('SELECT COUNT(*) FROM scores').fetchone()[0]
        snapshot = capture_report(service, 'AST-0001', ['M-STORAGE3', 'M-SPARES', 'M-INTAKE2'])
        self.assertEqual(snapshot['scenario']['score_after'], 50.2)
        self.assertEqual(snapshot['scenario']['capex_aed'], 725000000)
        self.assertEqual(snapshot['scenario']['opex_aed_per_year'], 7000000)
        self.assertEqual(service.records, before)
        self.assertEqual(service.db.execute('SELECT COUNT(*) FROM scores').fetchone()[0], rows_before)
        html = render_report(snapshot)
        parser = ReportParser(); parser.feed(html)
        evidence = json.loads(parser.payload)
        self.assertEqual(evidence, snapshot)
        self.assertEqual(len([i for i in parser.ids if i.startswith('asset-AST-')]), 60)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertEqual(len(evidence['dashboard']['facilities']), 60)
        for facility in evidence['dashboard']['facilities']:
            self.assertIn(facility['asset_id'], evidence['details'])
            self.assertIn(facility['result']['inputs_hash'], html)
        hash_content = {k: v for k, v in snapshot.items() if k not in ('generated_at', 'snapshot_hash')}
        self.assertEqual(snapshot['snapshot_hash'], 'sha256:' + hashlib.sha256(canonical(hash_content).encode()).hexdigest())
        service.rescore(BEFORE)
        self.assertEqual(evidence['details']['AST-0001']['record']['score'], 71)
        self.assertEqual(render_report(snapshot), html)

    def test_replay_reports_exclude_future_warnings_history_and_events(self):
        service = self.service
        warning = copy.deepcopy(service.adapter.warnings[-1]); warning['updated_at'] = '2026-08-28T06:30:00+04:00'
        service.ingest(warning)
        service.rescore(BEFORE)
        report = capture_report(service, 'AST-0001', ['M-INTAKE2', 'M-SPARES', 'M-STORAGE3'])
        self.assertEqual(report['details']['AST-0001']['record']['score'], 52)
        self.assertEqual(report['scenario']['score_after'], 36.7)
        self.assertFalse(report['dashboard']['events'])
        self.assertNotIn(warning, report['dashboard']['warning_log'])
        self.assertTrue(all(p['at'] <= BEFORE for d in report['details'].values() for p in d['history']))

    def test_snapshot_preserves_per_asset_compute_times_after_selective_update(self):
        self.service.rescore(BEFORE)
        before = {a: r['computed_at'] for a, r in self.service.records.items()}
        event = self.service.ingest(self.service.adapter.warnings[-1])
        report = capture_report(self.service)
        for f in report['dashboard']['facilities']:
            asset = f['asset_id']
            self.assertEqual(f['result']['computed_at'], event['at'] if asset in event['affected'] else before[asset])

    def test_safe_portable_html_preserves_unicode_and_hostile_source_strings(self):
        report = capture_report(self.service, 'AST-0001', scope='selected')
        payload = '</script><script>alert("unsafe")</script><img src="https://example.invalid/x">'
        report['dashboard']['facilities'][0]['name_en'] = payload
        html = render_report(report)
        parser = ReportParser(); parser.feed(html)
        self.assertEqual(len(parser.scripts), 2)
        self.assertEqual(parser.external, [])
        self.assertEqual(json.loads(parser.payload)['dashboard']['facilities'][0]['name_en'], payload)
        self.assertNotIn(payload, html)
        self.assertIn('محطة الساحل لتحلية المياه', html)
        self.assertIn('Risk-band distribution', html)
        self.assertIn('Risk versus consequence', html)
        self.assertIn('Historical risk score', html)
        self.assertIn('window.print()', html)

    def test_selected_scope_second_city_empty_data_and_invalid_requests(self):
        selected = render_report(capture_report(self.service, 'AST-0002', scope='selected'))
        self.assertEqual(selected.count('class="asset-profile"'), 1)
        self.assertIn('No measures selected', selected)
        for args in [('missing', [], 'portfolio'), ('AST-0002', ['M-SPARES'], 'portfolio'), ('AST-0001', [], 'invalid')]:
            with self.assertRaises(ValueError): capture_report(self.service, *args)
        second = Service(Adapter(ROOT / 'data_second_sample'), replay=False)
        try:
            report = capture_report(second)
            self.assertEqual(len(report['dashboard']['facilities']), 12)
            self.assertEqual(render_report(report).count('class="asset-profile"'), 12)
            self.assertEqual(report['sub_assets'], [])
        finally: second.db.close()
        empty = capture_report(self.service)
        empty['dashboard']['facilities'] = []; empty['selected_asset'] = None
        html = render_report(empty)
        self.assertIn('0 facilities / 0 sectors', html)
        self.assertNotIn('>nan<', html.lower())

    def test_routes_navigation_report_csp_and_bad_queries(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base) as response:
                home = response.read().decode(); self.assertIn('Enter the resilience atlas', home); self.assertIn('href="/dashboard"', home)
            for path in ('/dashboard', '/dashboard/', '/home.css', '/home.js'):
                with urlopen(base + path) as response: self.assertEqual(response.status, 200)
            with urlopen(base + '/report?asset=AST-0001&measure=M-INTAKE2&measure=M-SPARES&measure=M-STORAGE3') as response:
                html = response.read().decode()
                self.assertTrue(response.headers['Content-Type'].startswith('text/html'))
                csp = response.headers['Content-Security-Policy']
                import base64
                digest = base64.b64encode(hashlib.sha256(report_script().encode()).digest()).decode()
                self.assertIn("script-src 'sha256-" + digest + "'", csp)
                self.assertIn("connect-src 'none'", csp)
                parser = ReportParser(); parser.feed(html)
                self.assertEqual(json.loads(parser.payload)['scenario']['score_after'], 50.2)
            for query in ('asset=missing', 'scope=wrong', 'asset=AST-0002&measure=M-SPARES'):
                with self.assertRaises(HTTPError) as error: urlopen(base + '/report?' + query)
                self.assertEqual(error.exception.code, 400)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
