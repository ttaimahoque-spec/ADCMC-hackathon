# Validation record

Latest validation performed 17 November 2026 (GST), using Python 3.12 in the creation environment. Earlier model/chart inspections are retained below.

| Check | Result |
|---|---|
| `python -m unittest discover -s tests -v` | 45 tests passed in 15.890 seconds |
| 500-facility warning update | 0.422 seconds; all 500 affected records rescored |
| Plant baseline and warning scenario | 51.9 → 70.9; published 52 Elevated → 71 High |
| Plant confidence | 10/12 current inputs; grade B |
| Plant drivers | +19.0, +10.3, +4.7 |
| Individual example levers | 60.5, 66.2, 67.8, 69.4 |
| First three measures together | V 4.55, R 2.50, score 50.2 |
| Baseline warning state plus those measures | 36.7 Guarded |
| Trends at the example time | +19 over 7, 30 and 90 days |
| Sponsor portfolio reference | All 120 scores, one-decimal values, bands, overrides and confidence grades match |
| Sponsor pillar displays | Match within 0.01; rounding-boundary differences explicitly tolerated |
| Second sample | All 12 facilities load and produce schema-compatible records |
| Independent JSON Schema check | 1,147 input and demo-output records validated with the installed Draft 2020-12 validator |
| JavaScript | Syntax checks pass for the application scripts, including new landing-page and report actions |
| Map/chart behavior | All eight `node --test tests/test_visuals.js` checks pass: projection, real dependency edges, picking versus drag, camera controls, filtering, aggregation and escaping |
| Map rendering | Native Canvas renders inspected at 1050×500 and 360×370; all 60 facility points fit in the initial viewport, with five links for the selected plant |
| Architectural asset models | Seven `tests/test_asset3d.js` checks pass: 60 model inputs, ten families, 360° framing, depth occlusion, selection/tint, controls and animation lifecycle |
| Model rendering | Software renders inspected for desktop/mobile framing and opposite camera angles; WebGL/full-screen browser paths remain unverified |
| Fresh warning demo | `--demo-before` starts at 52, imports one new version, updates ten assets to produce plant score 71; source files and normal history are preserved |
| New model asset routes | HTTP route test passes for both JavaScript files and `asset-viewer.css` |
| Charts | Risk-band counts and sector counts account for all 60 facilities; one-facility and empty filters checked; source outputs remain unchanged |
| HTTP API and static assets | All tested routes return successfully; invalid requests and cross-origin writes rejected |
| External calls | None in the application; engine test denies socket creation |
| Real-browser rendering | Not verified; Chromium launch blocked by local socket restrictions |
| Hidden sponsor dataset | Not available; not tested |

`tests/browser_smoke.py` provides the remaining browser check for a local development machine: it checks replay, rotating model selection and appearance modes, pause controls, linked map/chart selection, empty and sector filters, map controls, combined measures, plans, methodology, warning feed, export, mobile overflow and browser errors. The environment had no bundled Playwright Chromium; a second attempt with installed Chromium failed at its required local socket. The full HTML/CSS layout and browser interactions remain unverified here. Canvas-only inspection and Node behavior tests are not substitutes for that browser check.

The redesigned map uses only the starter pack's local X/Y coordinates. Column height represents the published risk score, and color uses the engine's risk band (which may include an override). Dependency edges are supplied logical links, not real network routes. No map tiles, geocoding, external fonts, or online chart packages are used. Charts aggregate returned engine outputs; they do not implement another scoring model.

The test suite implements the supplied numerical and behavioral checks without substituting expected outputs into the engine. The schema validator is intentionally limited to the exact vocabulary in the unmodified sponsor schemas. No real facilities or external datasets were added.

The standalone architectural viewer is separate from the risk-column map. Model families are chosen from asset metadata; geometry is independent of scores and preserves the source data. The default material view uses synthetic facade, glass and roof colors. Risk tint uses only the overall supplied band and is not a component hazard/damage simulation. Animation is capped at 30 frames per second and pauses offscreen; reduced motion prevents autoplay. Mesh geometry is depth-buffered in WebGL or the local software fallback. Images from the references were used for design direction, not copied into the app as models or textures.


## Landing page and downloadable reports — 17 November 2026

- `/` and `/index.html` open the new landing page; `/dashboard` and `/dashboard/` open the workspace. All script/style references resolve to local packaged files and IDs are unique.
- Six new Python report tests pass for atomic snapshots, unchanged baseline/history, all 60 dossiers, exact selected-scenario outputs, earlier-date warning/history/event cutoffs, per-asset timestamps, 12-facility second sample, empty data rendering, invalid queries, Unicode, hostile text escaping and report security policy.
- Eighteen JavaScript tests pass in total: the existing 15 visual/model checks plus three report-action checks covering complete HTML download, evidence JSON, print expansion/restoration and offline navigation/scope selection.
- The default full report contains all 60 dossiers. The shorter report contains one dossier and retains complete portfolio charts/register. Selected measures yield 50.2, AED 725,000,000 capex and AED 7,000,000 annual opex in the official snapshot.
- The report includes its CSS, SVG charts, action script and JSON evidence inside one HTML file. Its content policy allows only the exact embedded action script and prevents network connections. A downloaded report does not require the Python app.
- Seven representative SVG report charts were rendered with MuPDF; sector and scenario bars and history labels were visually inspected. This validates those vector figures only, not the whole browser page.
- Chromium again could not launch because its local process socket was blocked. Landing-page browser layout, saved-file browser behavior and final PDF pagination remain unverified in this environment. The browser smoke script now covers landing navigation, report creation/download, file-mode reopening, evidence download, selected scope, print expansion/PDF generation and mobile overflow.
- PDF output uses the user's browser print dialog. There is no direct server-side PDF renderer and no additional application dependency. Page-counter support varies by browser.


## Compliance completion — 17 November 2026

- Model version is now `gen0-1.1.0`; generated before/after outputs and sensitivity records have been regenerated. All 120 supplied score, band and confidence references still match.
- Twelve new tests cover dated input ingestion, individual audit/control/continuity changes, negative change effects, identity-based row matching, additions/removals, metadata-only changes, consequence/population/exposure changes, replay cutoffs, prior-day comparison, restart persistence, validation and rollback, daily scheduling, adapter-only sub-asset loading and input HTTP routes. All 45 Python tests pass.
- Warning versions, affected score records and event logs now commit together. Source-input updates commit with a full portfolio run. Replaying an earlier date restores its facility/exposure/population version and excludes later updates from reports. Original input files remain unchanged.
- Replay backfill now computes full explanations rather than empty explanation arrays. The daily scheduler uses an injectable `daily_tick`; a simulated midnight test proves one full run and no duplicate run on the same day.
- The outbound-denied offline API check passed all 22 HTTP requests with zero external connections, including packaged resources, 52 to 71 warning ingestion, 50.2 scenario, report generation, dated input update and the second sample. This does not validate browser rendering or replace the laptop rehearsal.
- All 18 JavaScript tests pass after the backend changes. Application JavaScript syntax and Python compilation pass. The main dashboard design is retained; dated-input controls are in Warning feed and change evidence appears in History and reports.
- The one-page technical summary PDF was generated, its page count checked and its rendered page visually inspected. This PDF is generated separately from browser-printed dashboard reports.
- GitHub Actions now includes the new tests, an outbound-denied workflow and a Playwright browser job. GitHub was declined for this request; remote CI, repository upload and reviewer access are not claimed as completed.
- Chromium was retried and remains blocked by the environment's local socket restriction. Full browser/WebGL/report-print verification remains pending on a capable machine; no prerecorded demo video is claimed. The organizer's hidden dataset remains unavailable.
