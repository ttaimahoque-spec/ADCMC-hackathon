"""Optional real-browser checks: pip install playwright; playwright install chromium.

Run manually with: python -m tests.browser_smoke
Not part of the dependency-free unittest suite.
"""
import os
import threading
import json
import tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright, expect
from resilience.adapter import Adapter, ROOT
from resilience.service import Service
from run import make_handler


def main():
    service=Service(Adapter(ROOT/'data'))
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(service))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH'))
            context=browser.new_context(viewport={'width':1536,'height':1100})
            errors=[]; external=[]
            def check_route(route):
                from urllib.parse import urlparse
                url=urlparse(route.request.url)
                if url.scheme in ('http','https') and url.hostname not in ('127.0.0.1','localhost'):
                    external.append(route.request.url);route.abort()
                else:route.continue_()
            context.route('**/*',check_route)
            context.on('page',lambda p:p.on('pageerror',lambda e:errors.append(str(e))))
            page=context.new_page()
            page.goto(f'http://127.0.0.1:{server.server_port}')
            expect(page.locator('h1')).to_contain_text('resilient city')
            expect(page.locator('#home-count')).to_have_text('60')
            page.locator('.hero-actions a[href="/dashboard"]').click()
            expect(page.locator('#facility-rows tr')).to_have_count(60)
            expect(page.locator('.ring-num')).to_contain_text('71')
            expect(page.locator('#city-map')).to_have_attribute('data-point-count','60')
            expect(page.locator('#city-map')).to_have_attribute('data-visible-links','5')
            expect(page.locator('#band-chart .donut-number')).to_have_text('60')
            expect(page.locator('#sector-chart .sector-row')).to_have_count(9)
            expect(page.locator('#radar-chart .radar-name')).to_contain_text('Desalination')
            page.click('#map-top');expect(page.locator('#map-top')).to_have_text('3D')
            page.locator('#city-map').focus();page.keyboard.press('Home')
            expect(page.locator('#map-top')).to_have_text('2D')
            page.select_option('#map-focus','AST-0002')
            expect(page.locator('#detail .detail-topline')).to_contain_text('AST-0002')
            expect(page.locator('#radar-chart .radar-name')).to_have_text('Substation A')
            page.select_option('#map-focus','AST-0001')
            expect(page.locator('#detail .detail-topline')).to_contain_text('AST-0001')
            expect(page.locator('#asset-model')).to_have_attribute('data-asset-id','AST-0001')
            expect(page.locator('#asset-model')).to_have_attribute('data-model-type','plant')
            page.click('#model-rotate');expect(page.locator('#asset-model')).to_have_attribute('data-rotating','false')
            page.click('[data-model-mode="risk"]');expect(page.locator('#asset-model')).to_have_attribute('data-view-mode','risk')
            page.select_option('#model-focus','AST-0036')
            expect(page.locator('#asset-model')).to_have_attribute('data-model-type','tower')
            expect(page.locator('#detail .detail-topline')).to_contain_text('AST-0036')
            page.select_option('#model-focus','AST-0001')
            page.click('[data-model-mode="materials"]')
            page.click('#before');expect(page.locator('.ring-num')).to_contain_text('52')
            page.click('#after');expect(page.locator('.ring-num')).to_contain_text('71')
            page.fill('#search','desalination');expect(page.locator('#facility-rows tr')).to_have_count(1)
            expect(page.locator('#city-map')).to_have_attribute('data-point-count','1')
            expect(page.locator('#band-chart .donut-number')).to_have_text('1')
            page.fill('#search','no-such-facility')
            expect(page.locator('#city-map')).to_have_attribute('data-point-count','0')
            expect(page.locator('#band-chart .donut-number')).to_have_text('0')
            page.click('#reset-filters');expect(page.locator('#facility-rows tr')).to_have_count(60)
            page.click('#sector-chart [data-sector="health"]')
            expect(page.locator('#sector')).to_have_value('health')
            expect(page.locator('#map-selection')).to_contain_text('Outside current filters')
            page.click('#reset-filters')
            page.uncheck('#map-links');expect(page.locator('#city-map')).to_have_attribute('data-visible-links','0')
            page.check('#map-links');expect(page.locator('#city-map')).to_have_attribute('data-visible-links','5')
            page.click('[data-tab="measures"]')
            for measure in ['M-INTAKE2','M-SPARES','M-STORAGE3']:page.check(f'input[value="{measure}"]')
            expect(page.locator('#scenario-result .big')).to_have_text('50.2')
            with page.expect_popup() as popup:
                page.click('#report')
            report = popup.value
            report.wait_for_load_state()
            expect(report.locator('.asset-profile')).to_have_count(60)
            expect(report.locator('.scenario')).to_contain_text('725,000,000')
            assert report.locator('svg').count() >= 125
            payload = json.loads(report.locator('#report-data').text_content())
            assert payload['scenario']['score_after'] == 50.2
            with report.expect_download() as download:
                report.click('#download-report')
            assert download.value.suggested_filename == 'Sahil_Atlas_portfolio_2026-08-27.html'
            with tempfile.TemporaryDirectory() as temporary:
                saved = Path(temporary) / 'report.html'
                download.value.save_as(saved)
                offline = context.new_page()
                unexpected = []
                offline.on('request', lambda request: unexpected.append(request.url) if request.url.startswith(('http:', 'https:')) else None)
                offline.goto(saved.as_uri())
                expect(offline.locator('.online-actions')).to_be_hidden()
                expect(offline.locator('.asset-profile')).to_have_count(60)
                assert not unexpected, unexpected
                with offline.expect_download() as evidence:
                    offline.click('#download-evidence')
                evidence_path = Path(temporary) / 'evidence.json'
                evidence.value.save_as(evidence_path)
                assert json.loads(evidence_path.read_text()) == payload
                offline.close()
            report.click('#scope-link')
            expect(report.locator('.asset-profile')).to_have_count(1)
            expect(report.locator('.scenario')).to_contain_text('50.2')
            report.evaluate('window.dispatchEvent(new Event("beforeprint"))')
            assert report.locator('details[open]').count() == 1
            report.emulate_media(media='print')
            with tempfile.TemporaryDirectory() as temporary:
                report.pdf(path=str(Path(temporary) / 'selected-report.pdf'), prefer_css_page_size=True, print_background=True)
            report.close()
            page.click('[data-tab="plans"]');expect(page.locator('.plan').first).to_be_visible()
            page.click('[data-view="methodology"]');expect(page.locator('#sensitivity-results tbody tr')).to_have_count(6)
            page.click('[data-view="warnings"]');expect(page.locator('.warning-card').first).to_be_visible()
            with page.expect_download() as inputs_download:page.click('#inputs-template')
            assert inputs_download.value.suggested_filename=='asset-input-update.json'
            page.set_input_files('#inputs-file',str(ROOT/'examples/input_update_spares.json'))
            expect(page.locator('.event-log')).to_contain_text('input update')
            page.click('[data-view="overview"]')
            expect(page.locator('.ring-num')).to_contain_text('66')
            page.click('[data-tab="history"]')
            expect(page.locator('#detail')).to_contain_text('spares on site changed')
            page.click('#after');expect(page.locator('.ring-num')).to_contain_text('71')
            with page.expect_download() as download:page.click('#export')
            assert download.value.suggested_filename=='asset-resilience-scores.json'
            page.set_viewport_size({'width':390,'height':844})
            expect(page.locator('#city-map')).to_have_attribute('data-point-count','60')
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            page.goto(f'http://127.0.0.1:{server.server_port}')
            expect(page.locator('.hero-actions .cta')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            assert not errors,errors
            assert not external,external
            browser.close()
            print('Browser smoke checks passed.')
    finally:
        server.shutdown();server.server_close();service.db.close()


if __name__=='__main__':main()
