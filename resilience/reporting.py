"""Portable offline HTML reports with vector charts and a frozen evidence snapshot.

No third-party runtime packages. A browser supplies Print / Save as PDF.
Report creation is read-only and captures engine results under the service lock.
"""
import base64
import copy
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from html import escape
from .adapter import ROOT, canonical, timestamp

COLORS = {'Low': '#27866b', 'Guarded': '#397aaa', 'Elevated': '#a17c16', 'High': '#c56332', 'Severe': '#b64468'}
SECTORS = {'transport': 'Transport', 'health': 'Health', 'energy_water_wastewater': 'Energy / water / wastewater',
           'communications': 'Communications', 'waste': 'Waste', 'financial_services': 'Financial services',
           'security_and_safety': 'Security / safety', 'food': 'Food', 'government_facilities': 'Government facilities'}
PILLARS = {'T': 'Threat', 'V': 'Vulnerability', 'R': 'Recovery gap', 'C': 'Consequence'}


def capture_report(service, asset_id=None, measure_ids=None, scope='portfolio'):
    if scope not in ('portfolio', 'selected'):
        raise ValueError('Report scope must be portfolio or selected')
    with service.lock:
        asset_id = asset_id or next(iter(service.adapter.by_id), None)
        if asset_id is not None and asset_id not in service.adapter.by_id:
            raise ValueError('Unknown report asset')
        measure_ids = sorted(set(measure_ids or []))
        if measure_ids and not asset_id:
            raise ValueError('Select an asset before choosing measures')
        scenario = service.scenario(asset_id, measure_ids) if measure_ids else None
        dashboard = service.dashboard()
        # Do not expose later replay history or imported events in an earlier report.
        dashboard['events'] = [e for e in service.events if timestamp(e['at']) <= timestamp(service.at)]
        details = {f['asset_id']: service.detail(f['asset_id']) for f in service.adapter.facilities}
        snapshot = copy.deepcopy({
            'report_version': '1.0', 'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'scope': scope, 'selected_asset': asset_id, 'selected_measure_ids': measure_ids,
            'scenario': scenario, 'dashboard': dashboard, 'details': details,
            'measures': service.adapter.measures, 'exposures': service.adapter.exposures,
            'sub_assets': service.adapter.sub_assets, 'sensitivity': service.weight_sensitivity(),
            'input_updates': [u for u in service.input_updates if timestamp(u['effective_at']) <= timestamp(service.at)],
            'history_note': 'One latest score per recorded timestamp, limited to the snapshot time; repeat runs at one timestamp are collapsed.',
        })
    # Hash the frozen evidence, excluding only its generated timestamp and this hash.
    evidence = {k: v for k, v in snapshot.items() if k != 'generated_at'}
    snapshot['snapshot_hash'] = 'sha256:' + hashlib.sha256(canonical(evidence).encode('utf-8')).hexdigest()
    return snapshot


def e(value):
    return escape(str(value if value is not None else 'Not supplied'), quote=True)


def value_text(value):
    if value is None:
        return 'Not supplied'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    return str(value)


def label(key):
    return str(key).replace('_', ' ').capitalize()


def table(headers, rows, cls=''):
    rows = list(rows)
    if not rows:
        return '<p class="muted">No records supplied.</p>'
    return '<div class="table-wrap"><table class="' + cls + '"><thead><tr>' + ''.join('<th scope="col">' + e(h) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + e(value_text(c)) + '</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def fields(obj, prefix=''):
    """Every supplied source field, including extensions, without dropping nulls."""
    if isinstance(obj, dict) and obj:
        for key, value in obj.items():
            yield from fields(value, f'{prefix} / {label(key)}' if prefix else label(key))
    elif isinstance(obj, list) and obj:
        for index, value in enumerate(obj, 1):
            yield from fields(value, f'{prefix} [{index}]')
    else:
        yield prefix, 'None recorded' if obj == [] or obj == {} else value_text(obj)


def source_table(obj):
    return table(['Source field', 'Value'], fields(obj), 'source-table')


def figure(title, content, caption='', height=260):
    return f'<figure><h3>{e(title)}</h3><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 {height}" role="img" aria-label="{e(title)}"><title>{e(title)}</title>{content}</svg><figcaption>{e(caption)}</figcaption></figure>'


def text(x, y, content, size=12, anchor='start', color='#34465b'):
    return f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" fill="{color}">{e(content)}</text>'


def bars(title, rows, maximum=100, caption=''):
    rows = list(rows)
    if not rows:
        return f'<div class="chart-empty"><h3>{e(title)}</h3><p>No data available.</p></div>'
    height = 40 + 34 * len(rows)
    out = ''
    for index, (name, value, color) in enumerate(rows):
        y = 15 + index * 34
        out += text(0, y + 14, name, 11)
        out += f'<rect x="233" y="{y}" width="365" height="19" rx="3" fill="#edf1f3"/>'
        out += f'<rect x="233" y="{y}" width="{365 * max(0, min(maximum, value)) / max(1, maximum):.2f}" height="19" rx="3" fill="{color}"/>'
        out += text(612, y + 14, f'{value:g}', 12)
    out += text(233, height - 3, '0', 10) + text(598, height - 3, str(maximum), 10, 'end')
    return figure(title, out, caption, height)


def history_chart(points):
    if not points:
        return '<p class="muted">No historical score snapshots supplied.</p>'
    times = [timestamp(p['at']).timestamp() for p in points]
    span = max(times[-1] - times[0], 1)
    out = ''
    for score in (0, 25, 50, 75, 100):
        y = 190 - score * 1.6
        out += f'<line x1="40" x2="657" y1="{y}" y2="{y}" stroke="#dfe6e9"/>' + text(30, y + 4, score, 10, 'end')
    coords = [(40 + (t - times[0]) / span * 617, 190 - p['score'] * 1.6) for t, p in zip(times, points)]
    out += '<polyline fill="none" stroke="#27866b" stroke-width="2.5" points="' + ' '.join(f'{x:.2f},{y:.2f}' for x, y in coords) + '"/>'
    for index in set((0, len(coords) - 1)):
        x, y = coords[index]
        out += f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#27866b"/>'
        out += text(x, max(15, y - 9), points[index]['score'], 12, 'end' if index else 'start')
    out += text(40, 215, points[0]['at'][:10], 11) + text(657, 215, points[-1]['at'][:10], 11, 'end')
    return figure('Historical risk score', out, 'Published score / 100. History uses the static baseline plus explicitly dated input updates. Dates retain their source time zone.', 228)


def scatter_chart(facilities):
    out = ''
    for v in (0, 20, 40, 60, 80, 100):
        x = 50 + v * 5.9
        out += f'<line x1="{x}" x2="{x}" y1="25" y2="230" stroke="#e0e7e9"/>' + text(x, 249, v, 10, 'middle')
    for v in (0, 2, 4, 6, 8, 10):
        y = 230 - v * 20.5
        out += f'<line x1="50" x2="640" y1="{y}" y2="{y}" stroke="#e0e7e9"/>' + text(36, y + 4, v, 10, 'end')
    for f in facilities:
        r = f['result']
        out += f'<circle cx="{50 + r["score_exact"] * 5.9:.2f}" cy="{230 - r["pillars"]["C"] * 20.5:.2f}" r="4" fill="{COLORS[r["band"]]}" stroke="white" stroke-width=".6"><title>{e(f["name_en"])}: {r["score_exact"]}, C {r["pillars"]["C"]}</title></circle>'
    out += text(50, 13, 'Consequence / 10', 11) + text(345, 275, 'Risk score / 100', 11, 'middle')
    return figure('Risk versus consequence', out, 'Exact scores on the horizontal axis; color represents the assigned band, including category overrides.', 287)


def map_chart(facilities, selected_id):
    if not facilities:
        return ''
    xs = [f['location']['x_km'] for f in facilities]
    ys = [f['location']['y_km'] for f in facilities]
    project = lambda f: (40 + (f['location']['x_km'] - min(xs)) / max(max(xs) - min(xs), 1) * 600,
                         240 - (f['location']['y_km'] - min(ys)) / max(max(ys) - min(ys), 1) * 210)
    lookup = {f['asset_id']: f for f in facilities}
    out = '<rect x="40" y="30" width="600" height="210" fill="#f3f6f7"/>'
    for f in facilities:
        for dep in f.get('dependencies', []):
            upstream = lookup.get(dep['upstream_asset_id'])
            if upstream and selected_id in (f['asset_id'], upstream['asset_id']):
                x1, y1 = project(upstream)
                x2, y2 = project(f)
                out += f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#6a8f9b" stroke-width="1.5"/>'
    for f in facilities:
        x, y = project(f)
        out += f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{6 if f["asset_id"] == selected_id else 4}" fill="{COLORS[f["result"]["band"]]}" stroke="#172b3a" stroke-width="{2 if f["asset_id"] == selected_id else .4}"><title>{e(f["name_en"])} / {e(f["asset_id"])}</title></circle>'
    out += text(40, 15, f'Y {min(ys):g} to {max(ys):g} km', 11) + text(40, 262, f'X {min(xs):g} to {max(xs):g} km', 11)
    return figure('Facility locations and selected-asset links', out, 'Print-friendly plan view of fictional local coordinates. Lines are logical links touching the selected asset, not physical routes. Buildings are illustrative and are not survey evidence.', 280)


def profile(snapshot, f, focus=False):
    asset = f['asset_id']; r = f['result']; detail = snapshot['details'][asset]
    out = [f'<section class="asset-profile" id="asset-{e(asset)}"><div class="section-kicker">{"SELECTED ASSET" if focus else "ASSET DOSSIER"} / {e(asset)}</div><h2>{e(f["name_en"])}</h2><p class="arabic" lang="ar" dir="rtl">{e(f.get("name_ar", ""))}</p>']
    out.append(f'<div class="score-strip"><strong>{r["score"]}<small> / 100</small></strong><span style="color:{COLORS[r["band"]]}">{e(r["band"])} risk</span><span>Confidence {e(r["confidence"])}</span><span>Category {f["category"]}</span></div>')
    out.append(table(['Exact score (1 dp)', 'Current evidence', '7d / 30d / 90d change', 'Check-up proposed', 'Band override'],
                     [[r['score_exact'], f'{r["confidence_inputs"]["current"]} / {r["confidence_inputs"]["required"]}',
                       ' / '.join(value_text(r['trend'][f'd{d}']) for d in (7, 30, 90)), r['review']['proposed_checkup'], r['override_applied']]]))
    out.append(bars('Four pillars of risk', [(f'{k} / {name}', r['pillars'][k], '#27866b') for k, name in PILLARS.items()], 10, 'Higher is worse. Recovery gap is the inverse of recoverability.'))
    out.append('<h3>Score drivers</h3>' + table(['Factor', 'Kind', 'Effect (points)'], [(d['factor'], d['kind'], f'{d["effect"]:+.1f}') for d in r['drivers']]))
    out.append('<p class="note">Driver effects are separate counterfactuals; they must not be added together. A proposed check-up requires a human decision.</p>')
    out.append('<h3>Costed improvement options</h3>' + table(['Measure', 'Score after', 'Reduction', 'Capex AED', 'Opex AED / year', 'Modeled'],
        [(l['measure'], l['score_after'], l['reduction'], f'{l["capex_aed"]:,}', f'{l["opex_aed_per_year"]:,}', l['modeled']) for l in r['levers']]))
    if focus:
        out.append(scenario_section(snapshot, f))
    out.append('<h3>Dependent plans and assumptions</h3>' + table(['Plan / version / section', 'Reliance', 'Assumption'],
        [(f'{p["plan_id"]} / {p["plan_version"]} / {p["section_ref"]}', p['reliance'], p['assumption']) for p in detail['plans']]))
    out.append('<p class="note">Plan assumptions are supplied claims for analyst review, not verified current capabilities.</p>')
    out.append(history_chart(detail['history']))
    out.append('<h3>Evidence quality</h3>' + table(['Input', 'Current', 'Reason'], [(v['input'], v['current'], v['reason']) for v in r['confidence_inputs']['evidence']]))
    out.append('<h3>Computation audit</h3>' + table(['Field', 'Value'], [('Computed at', r['computed_at']), ('Model version', r['model_version']), ('Inputs hash', r['inputs_hash']), ('Acknowledged by', r['review']['acknowledged_by'])], 'source-table'))
    if r.get('input_changes'):
        out.append('<h3>Recorded source-input changes</h3><p class="note">Compared with ' + e(r['change_comparison']['as_of']) + '. Zero-point changes affect evidence or metadata only.</p>' + source_table(r['input_changes']))
    out.append('<h3>Facility source details</h3><p class="note">Includes ownership, operating status, coordinates, dependencies, audits, controls, continuity facts and provenance. All supplied fields are retained.</p>' + source_table({k: v for k, v in f.items() if k != 'result'}))
    exposures = [v for v in snapshot['exposures'] if v['asset_id'] == asset]
    out.append('<h3>Exposure evidence</h3>' + source_table(exposures))
    sub_assets = [v for v in snapshot['sub_assets'] if v.get('asset_id') == asset]
    out.append('<h3>Sub-assets</h3>' + (source_table(sub_assets) if sub_assets else '<p class="muted">No sub-asset records supplied.</p>'))
    measures = [v for v in snapshot['measures'] if v['asset_id'] == asset]
    if measures:
        out.append('<h3>Measure inputs, service life and changes</h3>' + source_table(measures))
    if detail['plans']:
        out.append('<h3>Full plan-link records</h3>' + source_table(detail['plans']))
    out.append('<details class="history-details"><summary>Dated history values (included in print)</summary>' + table(['Timestamp', 'Published risk score'], [(p['at'], p['score']) for p in detail['history']]) + '</details>')
    out.append('</section>')
    return ''.join(out)


def scenario_section(snapshot, f):
    result = snapshot['scenario']
    if not result:
        return '<div class="callout"><h3>Selected improvement scenario</h3><p>No measures selected when this report was created. Select measures in the dashboard, then create a new report to include a combined scenario.</p></div>'
    names = {m['measure_id']: m['name_en'] for m in snapshot['measures']}
    out = '<div class="scenario"><h3>Selected improvement scenario</h3><p>' + ' + '.join(e(names[m]) for m in snapshot['selected_measure_ids']) + '</p>'
    out += bars('Current versus combined scenario', [('Current exact score', f['result']['score_exact'], '#c56332'), ('Combined scenario', result['score_after'], '#27866b')], 100, 'Scenario recalculated by the scoring engine at the report snapshot; the baseline is unchanged.')
    out += table(['Band', 'Capex AED', 'Annual opex AED', 'Score reduction (points)', 'Band override'], [[result['band'], f'{result["capex_aed"]:,}', f'{result["opex_aed_per_year"]:,}', f'{f["result"]["score_exact"] - result["score_after"]:.1f}', result['override_applied']]])
    out += table(['T', 'V', 'R', 'C'], [[result['pillars'][k] for k in PILLARS]])
    return out + '<p class="note">Planning estimates from fictional data. Combined benefits are recomputed, not summed. No measures are implemented automatically.</p></div>'


def report_script():
    return (ROOT / 'web' / 'report.js').read_text(encoding='utf-8')


def report_csp():
    digest = base64.b64encode(hashlib.sha256(report_script().encode('utf-8')).digest()).decode()
    return f"default-src 'none'; script-src 'sha256-{digest}'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"


def render_report(snapshot):
    data = snapshot['dashboard']; facilities = sorted(data['facilities'], key=lambda f: (-f['result']['score_exact'], f['asset_id']))
    selected = next((f for f in facilities if f['asset_id'] == snapshot['selected_asset']), None)
    bands = Counter(f['result']['band'] for f in facilities)
    count = len(facilities)
    sectors = sorted(set(f['sector'] for f in facilities))
    report_name = 'Full portfolio report' if snapshot['scope'] == 'portfolio' else 'Selected asset report'
    scope_note = (f'All {count} facility dossiers, full portfolio charts and the selected scenario.' if snapshot['scope'] == 'portfolio'
                  else 'One detailed asset dossier, with full portfolio charts and the complete ranked register for context.')
    css = (ROOT / 'web' / 'report.css').read_text(encoding='utf-8')
    csp = report_csp().replace("; frame-ancestors 'none'", '')
    out = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="{e(csp)}"><title>Sahil Atlas - {report_name} - {e(data["at"][:10])}</title><style>{css}</style></head><body>']
    out.append('<header class="report-tools"><div><strong>SAHIL ATLAS</strong><span>Report preview</span></div><nav aria-label="Report actions"><button id="download-report">Download HTML report</button><button id="print-report" class="primary">Print / Save as PDF</button><button id="download-evidence">Download evidence JSON</button></nav></header>')
    out.append('<div class="preview-note"><p>This is a fixed snapshot. The download includes graphs and evidence and opens without the app. For a PDF, choose Print / Save as PDF, then select your browser’s PDF destination. No download happens until you choose a button.</p><div class="online-actions"><a href="/dashboard">← Back to dashboard</a><a id="scope-link" href="/report">Switch report scope</a></div><noscript>Use your browser’s Print or Save Page command. Charts and data do not require JavaScript.</noscript></div>')
    out.append(f'<main><section class="report-cover"><div class="section-kicker">CHALLENGE 01 / DECISION SUPPORT</div><h1>Asset resilience<br><span>{e(report_name)}</span></h1><p class="city">{e(data["city"].get("city_en", "City workspace"))}</p><p>{e(scope_note)}</p><dl><dt>Portfolio snapshot</dt><dd>{e(data["at"])}</dd><dt>Report generated (UTC)</dt><dd>{e(snapshot["generated_at"])}</dd><dt>Selected asset</dt><dd>{e(selected["name_en"] if selected else "None")}</dd><dt>Coverage</dt><dd>{count} facilities / {len(sectors)} sectors. Dashboard filters do not restrict this report.</dd></dl><p class="hash">Snapshot hash: {e(snapshot["snapshot_hash"])}</p><p class="note">Fictional facilities and illustrative asset geometry. Higher scores mean higher risk, not failure probability. Confidence measures evidence quality separately. Each asset retains its own computation time; warning updates may leave unaffected records at earlier times.</p></section>')
    out.append('<nav class="contents" aria-label="Report contents"><a href="#portfolio">01 Portfolio overview</a><a href="#register">02 Asset register</a><a href="#dossiers">03 Asset dossiers & scenario</a><a href="#warnings">04 Warnings & events</a><a href="#methodology">05 Methodology & sensitivity</a></nav>')
    mean = sum(f['result']['score_exact'] for f in facilities) / max(count, 1)
    current = sum(f['result']['confidence_inputs']['current'] for f in facilities)
    required = sum(f['result']['confidence_inputs']['required'] for f in facilities)
    out.append('<section id="portfolio" class="major"><div class="section-kicker">01 / PORTFOLIO OVERVIEW</div><h2>The current risk landscape</h2>')
    out.append('<div class="metrics">' + ''.join(f'<div><strong>{e(v)}</strong><span>{e(k)}</span></div>' for k, v in [('Facilities', count), ('High / severe', bands['High'] + bands['Severe']), ('Mean exact score', f'{mean:.1f}'), ('Current evidence', f'{100 * current / required:.1f}%' if required else 'Not available')]) + '</div>')
    out.append('<p class="note">Mean uses exact-score values reported by the engine (one decimal). Current evidence is weighted by required inputs. Whole-point scores remain the published facility scores.</p>')
    out.append(bars('Risk-band distribution', [(b, bands[b], color) for b, color in COLORS.items()], max(1, count), 'Facility counts; includes category overrides.'))
    sector_rows = []
    for sector in sectors:
        values = [f['result']['score_exact'] for f in facilities if f['sector'] == sector]
        sector_rows.append((SECTORS.get(sector, label(sector)), round(sum(values) / len(values), 1), '#397aaa'))
    out.append(bars('Average risk by sector', sorted(sector_rows, key=lambda row: -row[1]), 100, 'Mean exact-score value per sector. Risk scale 0 to 100.'))
    out.append(scatter_chart(facilities))
    out.append(map_chart(facilities, snapshot['selected_asset']))
    out.append('<p class="legend">' + ' · '.join(f'<span style="color:{color}">{e(band)}</span>' for band, color in COLORS.items()) + '</p></section>')
    out.append('<section id="register" class="major"><div class="section-kicker">02 / COMPLETE ASSET REGISTER</div><h2>Priority order</h2>')
    out.append(table(['Rank / asset', 'Facility / sector', 'Category', 'Score / exact', 'Band', 'Confidence', 'Review'], [
        [f'{index} / {f["asset_id"]}', f'{f["name_en"]} / {SECTORS.get(f["sector"], f["sector"])}', f['category'], f'{f["result"]["score"]} / {f["result"]["score_exact"]}', f['result']['band'], f['result']['confidence'], f['result']['review']['proposed_checkup']]
        for index, f in enumerate(facilities, 1)]))
    out.append('</section><section id="dossiers" class="major"><div class="section-kicker">03 / ASSET DOSSIERS</div><h2>Evidence behind the scores</h2><p>The selected asset appears first. Dossiers include score drivers, individual options, plans, history, confidence, full source fields and computation audit data.</p></section>')
    if selected:
        out.append(profile(snapshot, selected, focus=True))
    if snapshot['scope'] == 'portfolio':
        for f in facilities:
            if f['asset_id'] != snapshot['selected_asset']:
                out.append(profile(snapshot, f))
    out.append('<section id="warnings" class="major"><div class="section-kicker">04 / WARNINGS AND EVENTS</div><h2>Warning evidence</h2><h3>Open warnings at the snapshot</h3>')
    out.append(table(['Risk ID / title', 'Level', 'Likelihood', 'Channels', 'Coverage', 'Updated at'], [(f'{w["risk_id"]} / {w["title"]}', w['warning_level'], w['likelihood'], ', '.join(map(str, w['channels'])), w['coverage'], w['updated_at']) for w in data['warnings']]))
    out.append('<h3>Channel definitions</h3>' + source_table(data['channels']))
    out.append('<h3>Complete warning version log through this snapshot</h3>' + source_table(data['warning_log']))
    out.append('<h3>Import events through this snapshot</h3>' + source_table(data['events']) + '<h3>Dated source-input updates</h3>' + source_table(snapshot['input_updates']) + '</section>')
    out.append('<section id="methodology" class="major"><div class="section-kicker">05 / METHODOLOGY & ROBUSTNESS</div><h2>How to read this report</h2><p class="formula">Risk = 100 × (T × V × R × C / 10,000)<sup>¼</sup></p><p>All four pillars range from 0 to 10. Threat combines exposed warning channels. Vulnerability weights audit condition, control gaps and irreplaceability at 40%, 30% and 30%. Recovery gap is ten times one minus the mean of six recovery facts. Consequence uses the maximum category, supply-share and population-share score.</p><p>Published scores are rounded to whole points. Low: 0–19; Guarded: 20–39; Elevated: 40–59; High: 60–79; Severe: 80–100. Category 1–2 assets with T, V or R at least 9 receive a minimum High band. Confidence: A at least 90%, B at least 75%, C at least 50%, otherwise D of required inputs current.</p><h3>Vulnerability-weight sensitivity (±20%)</h3>')
    out.append(table(['Weight change', 'Normalized A / C / I weights', 'Facilities moved', 'Largest rank move'], [(v['label'], ' / '.join(f'{w * 100:.1f}%' for w in v['weights']), v['moved'], v['max_movement']) for v in snapshot['sensitivity']]))
    for v in snapshot['sensitivity']:
        out.append('<h4>' + e(v['label']) + ' / rank changes</h4>' + table(['Asset', 'Baseline rank', 'Scenario rank', 'Movement'], [(c['asset_id'], c['baseline'], c['rank'], c['movement']) for c in v['changes'] if c['movement']]))
    out.append('<h3>Assumptions and limitations</h3><ul><li>City and asset data are fictional. The dashboard’s 3D models are illustrative; this report uses a vector plan view for legible printing.</li><li>History uses the supplied static baseline, warning versions and explicitly dated input updates. It cannot reconstruct unrecorded changes. One latest score per recorded timestamp is shown, with repeat runs collapsed.</li><li>Unknown audits and controls receive conservative scores. Unknown recovery facts earn no recovery credit. Evidence freshness and channel coverage affect confidence separately.</li><li>Full exercises are treated as current because no exercise date is supplied. Driver effects are separate counterfactuals; intervention benefits are recomputed jointly.</li><li>Some reference pillar displays differ by 0.01 at rounding boundaries. This report preserves engine outputs.</li><li>Plan assumptions require human verification. A proposed check-up is a recommendation for analyst review.</li><li>The saved HTML includes a complete structured evidence snapshot. Use Download evidence JSON for machine-readable values, including every current score record and all dated chart points. A printed PDF contains the visible report, not the embedded JSON attachment.</li></ul><h3>City metadata</h3>' + source_table(data['city']) + '</section>')
    out.append('<footer>SAHIL ATLAS / CHALLENGE 01 · Offline report · Analyst decision support</footer></main>')
    # JSON must not terminate its script container, even for arbitrary hidden datasets.
    payload = json.dumps(snapshot, ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    out.append('<script id="report-data" type="application/json">' + payload + '</script><script>' + report_script() + '</script></body></html>')
    return ''.join(out)
