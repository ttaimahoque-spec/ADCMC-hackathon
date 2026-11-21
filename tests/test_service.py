import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from resilience.adapter import Adapter, ROOT, parse_json, validate
from resilience.engine import score_record
from resilience.service import Service, BEFORE, AFTER
from run import make_handler, create_service


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.adapter=Adapter(ROOT/'data')
        self.service=Service(self.adapter,at=BEFORE,replay=False)

    def tearDown(self):
        self.service.db.close()

    def test_warning_update_only_touches_exposed_facilities(self):
        before=dict(self.service.records)
        warning=next(w for w in self.adapter.warnings if w['updated_at']=='2026-08-27T06:30:00+04:00')
        event=self.service.ingest(warning)
        affected={e['asset_id'] for e in self.adapter.exposures if e['channel_id']==2 and e['exposed']}
        self.assertEqual(set(event['affected']),affected)
        self.assertEqual(self.service.records['AST-0001']['score'],71)
        for asset in before:
            if asset not in affected:self.assertIs(self.service.records[asset],before[asset])

    def test_channel_move_updates_old_and_new_exposures(self):
        warning=copy.deepcopy(self.adapter.warnings[1])
        warning.update(channels=[5],updated_at='2026-08-26T21:00:00+04:00')
        event=self.service.ingest(warning)
        affected={e['asset_id'] for e in self.adapter.exposures if e['channel_id'] in (2,5) and e['exposed']}
        self.assertEqual(set(event['affected']),affected)

    def test_invalid_batch_is_atomic(self):
        snapshot=copy.deepcopy(self.service.records)
        warning=copy.deepcopy(self.adapter.warnings[1]);warning['likelihood']=2
        with self.assertRaises(ValueError):self.service.ingest([self.adapter.warnings[0],warning])
        self.assertEqual(snapshot,self.service.records)
        with self.assertRaises(ValueError):self.service.ingest({'risk_id':'missing fields'})
        with self.assertRaises(ValueError):parse_json('[NaN]')

    def test_conflicting_warning_version_rejected(self):
        warning=copy.deepcopy(self.adapter.warnings[1]);warning['title']='Conflicting version'
        with self.assertRaises(ValueError):self.service.ingest(warning)

    def test_scenarios_do_not_mutate_baseline(self):
        self.service.rescore(AFTER)
        before=copy.deepcopy(self.adapter.facilities)
        result=self.service.scenario('AST-0001',['M-INTAKE2','M-SPARES','M-STORAGE3'])
        self.assertEqual(result['score_after'],50.2)
        self.assertEqual(result['capex_aed'],725_000_000)
        self.assertEqual(self.adapter.facilities,before)
        self.assertEqual(self.service.records['AST-0001']['score'],71)
        with self.assertRaises(ValueError):self.service.scenario('AST-0002',['M-SPARES'])

    def test_500_facility_warning_benchmark(self):
        adapter=Adapter(ROOT/'data')
        template=copy.deepcopy(adapter.facilities[0])
        exps=copy.deepcopy(adapter.exposure_index['AST-0001'])
        adapter.facilities=[];adapter.exposures=[];adapter.exposure_index={};adapter.by_id={}
        adapter.measures=[];adapter.plan_links=[];adapter.pilot=[]
        for i in range(500):
            asset=f'AST-{i+1:04d}'
            f=copy.deepcopy(template);f['asset_id']=asset
            adapter.facilities.append(f);adapter.by_id[asset]=f
            rows=copy.deepcopy(exps)
            for row in rows:row['asset_id']=asset
            adapter.exposure_index[asset]=rows;adapter.exposures.extend(rows)
        service=Service(adapter,at=BEFORE,replay=False)
        warning=copy.deepcopy(adapter.warnings[-1])
        start=time.perf_counter();event=service.ingest(warning);elapsed=time.perf_counter()-start
        self.assertEqual(len(event['affected']),500)
        self.assertLess(elapsed,60)
        self.assertTrue(all(r['score']==71 for r in service.records.values()))
        print(f'\n500-facility warning update: {elapsed:.3f}s')
        service.db.close()

    def test_warning_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            db=str(Path(temp)/'history.sqlite3')
            service=Service(Adapter(ROOT/'data'),db,at=AFTER,replay=False)
            warning=copy.deepcopy(service.adapter.warnings[-1]);warning['updated_at']='2026-08-28T06:30:00+04:00'
            warning.update(likelihood=.5,likelihood_high=.6)
            service.ingest(warning);first=service.records['AST-0001']['score'];service.db.close()
            restored=Service(Adapter(ROOT/'data'),db,at=warning['updated_at'],replay=False)
            self.assertEqual(restored.records['AST-0001']['score'],first)
            self.assertEqual(len(restored.events),1)
            restored.db.close()
            with self.assertRaisesRegex(ValueError,'another dataset'):
                Service(Adapter(ROOT/'data_second_sample'),db,at=AFTER,replay=False)

    def test_schema_validator_rejects_wrong_types_and_accepts_extensions(self):
        score=copy.deepcopy(self.service.records['AST-0001'])
        score['score']=True
        with self.assertRaises(ValueError):validate(score,self.adapter.schemas['score'])
        score['score']=52;score['optional_extension']={'anything':'preserved'}
        validate(score,self.adapter.schemas['score'])

    def test_http_routes_and_errors(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.service))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base+'/api/state') as response:
                self.assertEqual(len(json.load(response)['facilities']),60)
            for route in ['/','/styles.css','/asset-viewer.css','/asset3d.js','/asset-renderer.js','/map3d.js','/visuals.js','/app.js','/favicon.svg','/api/detail?asset=AST-0001','/api/export','/api/sensitivity']:
                with urlopen(base+route) as response:self.assertEqual(response.status,200)
            for route in ['/../../data/facilities.json','/data/facilities.json']:
                with self.assertRaises(HTTPError) as error:urlopen(base+route)
                self.assertEqual(error.exception.code,404)
            data=json.dumps({'asset_id':'AST-0001','measure_ids':['M-SPARES']}).encode()
            req=Request(base+'/api/scenario',data=data,headers={'Content-Type':'application/json'})
            with urlopen(req) as response:self.assertIn('score_after',json.load(response))
            bad=Request(base+'/api/warnings',data=b'{"risk_id":"bad"}',headers={'Content-Type':'application/json'})
            with self.assertRaises(HTTPError) as error:urlopen(bad)
            self.assertEqual(error.exception.code,400)
            cross=Request(base+'/api/scenario',data=data,headers={'Content-Type':'application/json','Origin':'https://external.example'})
            with self.assertRaises(HTTPError) as error:urlopen(cross)
            self.assertEqual(error.exception.code,403)
        finally:
            server.shutdown();server.server_close();thread.join()


class ReplayTests(unittest.TestCase):
    def test_fresh_demo_import_is_new_and_restart_is_repeatable(self):
        warning=parse_json((ROOT/'examples/warning_red.json').read_text())
        source=(ROOT/'data/warnings.json').read_bytes()
        for _ in range(2):
            service=create_service(ROOT/'data',demo_before=True,replay=False)
            try:
                self.assertEqual(service.records['AST-0001']['score'],52)
                before=dict(service.records)
                event=service.ingest(warning)
                self.assertEqual(event['versions'],1)
                self.assertEqual(len(event['affected']),10)
                self.assertEqual(service.records['AST-0001']['score'],71)
                for asset in set(before)-set(event['affected']):
                    self.assertIs(service.records[asset],before[asset])
                self.assertEqual(service.scenario('AST-0001',['M-INTAKE2','M-SPARES','M-STORAGE3'])['score_after'],50.2)
                self.assertEqual(service.db.execute('PRAGMA database_list').fetchone()[2],'')
            finally:
                service.db.close()
        self.assertEqual((ROOT/'data/warnings.json').read_bytes(),source)
        with self.assertRaisesRegex(ValueError,'omit --db'):
            create_service(ROOT/'data',database='not-created.sqlite3',demo_before=True,replay=False)

    def test_full_replay_demo_trends(self):
        service=Service(Adapter(ROOT/'data'))
        row=service.records['AST-0001']
        self.assertEqual(row['trend'],{'d7':19,'d30':19,'d90':19})
        self.assertTrue(row['review']['proposed_checkup'])
        self.assertEqual(len(row['dependent_plans']),3)
        self.assertGreater(len(service.history['AST-0001']),90)
        service.db.close()


if __name__=='__main__':unittest.main()
