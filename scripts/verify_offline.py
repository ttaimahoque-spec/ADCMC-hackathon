#!/usr/bin/env python3
"""Exercise the local application while denying outbound network connections.

Python standard library only. Run from any directory with py scripts/verify_offline.py.
This verifies APIs and packaged resources; it does not replace browser/laptop QA.
"""
import ipaddress
import json
import socket
import sys
import threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler
from unittest.mock import patch
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from resilience.adapter import Adapter, parse_json, validate
from resilience.service import Service, AFTER
from run import create_service, make_handler


class PageResources(HTMLParser):
    def __init__(self): super().__init__(); self.resources = []; self.in_data = False; self.data = ''
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'img', 'link'):
            url = attrs.get('src') or attrs.get('href')
            if url: self.resources.append(url)
        if tag == 'script': self.in_data = attrs.get('id') == 'report-data'
    def handle_endtag(self, tag):
        if tag == 'script': self.in_data = False
    def handle_data(self, value):
        if self.in_data: self.data += value


def verify():
    denied = []; seen = []
    original_connect = socket.socket.connect
    def local_only(sock, address):
        host = address[0] if isinstance(address, tuple) else ''
        try: permitted = ipaddress.ip_address(host).is_loopback
        except ValueError: permitted = host == 'localhost'
        if not permitted:
            denied.append(str(address)); raise AssertionError('Outbound network request denied')
        return original_connect(sock, address)
    with patch.object(socket.socket, 'connect', local_only):
        service = create_service(ROOT / 'data', demo_before=True)
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(service))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        opener = build_opener(ProxyHandler({}))
        base = f'http://127.0.0.1:{server.server_port}'
        def call(path, body=None, raw=False):
            request = Request(base + path, data=None if body is None else json.dumps(body).encode(),
                              headers={} if body is None else {'Content-Type': 'application/json'})
            with opener.open(request, timeout=30) as response: data = response.read()
            seen.append(path)
            return data.decode('utf-8') if raw else json.loads(data)
        try:
            pending = ['/', '/dashboard']; checked = set()
            while pending:
                path = pending.pop()
                if path in checked: continue
                checked.add(path); body = call(path, raw=True)
                if path in ('/', '/dashboard'):
                    parser = PageResources(); parser.feed(body)
                    for url in parser.resources:
                        assert url.startswith('/') and not url.startswith('//'), url
                        pending.append(url)
            state = call('/api/state'); assert state['facilities'][0]['result']['score'] == 52
            event = call('/api/warnings', parse_json((ROOT / 'examples/warning_red.json').read_text(encoding='utf-8')))
            assert event['versions'] == 1 and len(event['affected']) == 10
            assert call('/api/detail?asset=AST-0001')['record']['score'] == 71
            call('/api/replay', {'phase': 'after'})
            scenario = call('/api/scenario', {'asset_id': 'AST-0001', 'measure_ids': ['M-INTAKE2', 'M-SPARES', 'M-STORAGE3']})
            assert scenario['score_after'] == 50.2 and scenario['capex_aed'] == 725000000
            scores = call('/api/export'); assert len(scores) == 60
            for score in scores: validate(score, service.adapter.schemas['score'])
            html = call('/report?scope=selected&asset=AST-0001&measure=M-INTAKE2&measure=M-SPARES&measure=M-STORAGE3', raw=True)
            report = PageResources(); report.feed(html)
            assert not report.resources
            assert json.loads(report.data)['scenario']['score_after'] == 50.2
            update = call('/api/input-template?asset=AST-0001')
            update['effective_at'] = '2026-08-28T06:40:00+04:00'; update['facilities'][0]['continuity']['spares_on_site'] = True
            call('/api/inputs', update)
            updated = call('/api/detail?asset=AST-0001')['record']
            assert updated['score_exact'] == 66.2
            assert any(c['factor'] == 'Continuity: spares on site changed' for c in updated['input_changes'])
            second = Service(Adapter(ROOT / 'data_second_sample'), replay=False)
            try:
                assert len(second.records) == 12
                for record in second.records.values(): validate(record, second.adapter.schemas['score'])
            finally: second.db.close()
            assert not denied, denied
            return {'status': 'passed', 'checked_http_requests': len(seen), 'external_connections': len(denied),
                    'baseline': 52, 'after_warning': 71, 'scenario': 50.2, 'input_update_score': 66.2,
                    'second_sample_facilities': 12, 'browser_rendering': 'separate check required'}
        finally:
            server.shutdown(); server.server_close(); thread.join(); service.db.close()

if __name__ == '__main__': print(json.dumps(verify(), indent=2))
