# Sahil Atlas · Asset Resilience Dashboard

A local dashboard for Challenge 01: rank critical facilities, explain their risk, replay warnings and compare costed resilience measures. It includes the supplied fictional city, all 60 facilities, a deterministic Python scoring engine and a responsive browser interface. The redesigned Sahil Atlas interface uses a dark navy theme, an interactive 3D risk map, a rotating architectural asset viewer inspired by the supplied reference images, and linked portfolio visuals.

**Keep this repository private.** The supplied ADCMC brief restricts the pack and submitted work to you and ADCMC. Do not publish it on a public repository, GitHub Pages or a public demo service.

## Run in one command

Install Python **3.10 or newer**, then run this command from the extracted project folder:

```bash
python3 run.py
```

On Windows, use `py run.py` if `python3` is unavailable. Open **http://127.0.0.1:8000**. First launch replays the warning history with full explanations; allow roughly 15 seconds, depending on the computer. Subsequent launches reuse the local history. Stop with Ctrl+C.

There are **no third-party application dependencies**, no API keys, no package installation, no CDN assets and no internet calls at runtime. Python is the prerequisite. The browser talks only to the local server. The initial view is 27 August 2026, 06:40 GST, so the example remains reproducible regardless of today's date.

For this update, extract the ZIP into a **new folder**, stop the old server with Ctrl+C, and run the new copy. Your original folder and its saved history remain intact. Refresh the browser with Ctrl+F5 if the old style is cached.

## Landing page and dashboard

Opening **http://127.0.0.1:8000** now shows a dedicated landing page with the rotating asset model, a short workflow introduction and reporting overview. Choose **Open dashboard** or **Enter the resilience atlas** to open the existing workspace at **http://127.0.0.1:8000/dashboard**. The dashboard brand returns to the landing page. The home-page counts use the loaded dataset, including the second sample.

## Download a report with graphs and full details

1. Open the dashboard, choose the snapshot and select a facility. If desired, open **Measures** and select the improvements to include.
2. Click **Create report** at the top of the dashboard. A new tab displays a fixed snapshot of the entire portfolio; dashboard filters do not reduce its scope.
3. Choose **Download HTML report** for a single file containing the graphs, report layout and complete structured evidence. It opens offline after the server is stopped, with no companion files.
4. Choose **Print / Save as PDF**, select **Save as PDF** (or **Microsoft Print to PDF**) in your browser's print dialog, then save. This uses the browser's built-in PDF printer; it is not a direct server-generated PDF download. The print layout uses a white background, A4 pages, repeating table headers and vector charts. Use 100% scale; disable browser headers/footers if they duplicate the report's page labels. Page counters depend on browser support.
5. **Download evidence JSON** preserves the full machine-readable snapshot. This includes current scores, facility inputs, dated history values, warnings, plans, measure changes, sensitivity and audit hashes. The printed PDF contains visible report content, not the embedded JSON as an attachment.

The default **Full portfolio report** includes all facility dossiers and is deliberately comprehensive. For a shorter presentation handout, use **Create a shorter selected-asset report** in the preview. It retains the portfolio charts and full ranked register, while limiting detailed dossiers to the selected asset. Switching scope creates a new snapshot from the running app and preserves the selected measures.

Both versions include the risk distribution, sector averages, score-versus-consequence chart, a print-friendly coordinate map, pillar bars, score history and the selected scenario comparison. Dossiers include ownership, operating status, dependencies, all audit/control/continuity/provenance fields, exposure evidence, sub-assets where supplied, confidence reasons, plan claims, costs, modeled changes, review state, model version, input hash and computation time. Dated history tables are expandable on screen and open automatically for printing. Individual measures with no supplied input changes are labeled unmodeled.

Reports are read-only: they neither change the underlying facilities nor append scores. Data is captured under one service lock, then rendered from an independent snapshot. Future warnings, events and history are excluded when reporting an earlier replay time. Unaffected assets keep their original computation timestamps after a selective warning update. The report states the portfolio snapshot and generation times separately. The snapshot hash covers the embedded evidence except `generated_at` and the hash itself.

See [the reporting guide](docs/REPORT_GUIDE.md) for a short demonstration and print checklist.

## Explore a rotating building or asset

The main **360° Explorer** presents a standalone, shaded 3D asset beside its facility profile. It uses actual three-dimensional meshes with windows, doors, roof equipment, tanks, pipes, towers or other details appropriate to an illustrative asset type. WebGL supplies depth-buffered rendering; a software renderer works when WebGL is unavailable. Both run entirely offline, with no model downloads or extra packages.

1. Select a facility in the viewer dropdown, map or priority table. **Al Sahil Desalination Plant** shows a treatment plant; **Main Bank Operations Centre** shows a tall office building; **Al Sahil General Hospital** shows a healthcare complex.
2. The model rotates automatically. **Pause rotation** freezes it; **Rotate model** starts it again. Dragging also pauses rotation, allowing precise inspection. Arrow keys rotate and tilt, Space toggles motion, and Home resets the camera.
3. Use **+ / −** to zoom, **↺** to reset, or the expand button to use the full screen where supported. After focusing the canvas, the mouse wheel also zooms. Escape exits full screen.
4. **Materials** shows facade, glass, metal and roof colors. **Risk tint** colors the model using the facility's existing overall risk band. The model dimensions never change with the score.
5. The buttons below the model highlight illustrative building, equipment or site groups. Click the active group again to return to the complete model.

Ten model families cover the supplied facilities: commercial buildings, office towers, hospitals, warehouses, treatment plants, substations, storage infrastructure, communications sites, bridges and solar facilities. Shapes are selected from facility names/sectors and include a generic fallback for new facilities. They are **illustrations, not surveyed building models or calibrated digital twins**. Geometry and depicted equipment are not asset evidence. No facade temperature, flood level, component damage or loss estimates are invented. The original map below the charts remains a score-height geographic view of the supplied fictional coordinates.

Automatic rotation pauses while the viewer is offscreen, its tab is hidden or another dashboard view is open. Reduced-motion preferences disable autoplay; the user can start it explicitly. The viewer remains usable with touch, keyboard controls and software rendering.

## Explore the 3D atlas and visuals

- **3D facility map:** drag to orbit and tilt, use + / − to zoom, choose 2D for a view from above, and use ↺ to reset. The orbit and tilt sliders provide another way to control the view. With the canvas focused, arrow keys rotate/tilt, + / − zoom, and Home resets.
- **Facility selection:** click a column, use the map's facility dropdown, or choose a row in the priority table. The facility profile and pillar chart follow the selection.
- **Dependencies:** blue arrows enter the selected asset from its upstream providers; mint arrows lead toward downstream dependents. Only supplied relationships between visible facilities are drawn. Toggle links or labels independently.
- **Risk distribution:** a donut and counts show the risk bands among filtered facilities, including category overrides.
- **Sector comparison:** horizontal bars show mean exact risk scores. Click a sector to filter; click it again or use Reset to clear that filter.
- **Pillar profile:** the selected asset is compared with the filtered portfolio mean on the 0–10 T/V/R/C scale. Expand “View pillar values” for a text table.
- **Scenario comparison:** the Measures tab includes current-versus-scenario bars using the Python engine's returned scores. The review scatterplot and History tab provide additional views.

The map uses the supplied **fictional local X/Y coordinates**, not a real-world basemap. Column height encodes the published risk score; color encodes the risk band, including overrides. Columns are not real building dimensions or elevations. The native Canvas renderer projects three-dimensional geometry without external map services. Filtering does not change the map's coordinate extent or the source records.

## Record changing asset inputs

The existing dashboard design is preserved. In **Warning feed**, **Asset inputs** downloads a JSON template for the selected facility. Edit the full facility record, signed exposure records and `effective_at` timestamp, then use **Load asset inputs**. The timestamp must include an offset and cannot precede the active snapshot. Later versions must use a later timestamp; importing the same file twice has no effect.

For a reproducible example, start normally, select the plant and load `examples/input_update_spares.json` from **Warning feed → Load asset inputs**. At 28 August 2026, 06:40 GST, the source record states spares are on site and the exact score becomes **66.2**. The **History** tab lists the input change and its effect. This updates a source fact supplied in a file; it does not execute an intervention. Scenarios in **Measures** remain hypothetical and never update source facts.

Input updates are recorded in SQLite with a full portfolio scoring run in one transaction. The original data files are preserved. Replaying **Before warning** or **After warning** restores the inputs effective at that earlier date. Later input versions, events and history are excluded from earlier reports. Ordinary warning imports still rescore only the affected assets, including any dated input changes that become effective as the snapshot advances.

The update envelope accepts `effective_at` plus any of `facilities` (full existing-asset records), `exposures` (full asset/channel records) and `population` (a positive integer). Omitted fields stay unchanged. Provided facility and exposure records replace their earlier versions; unknown asset/channel references and duplicate entries are rejected. Signed exposure evidence comes from the supplied/operator-authored records, never generated by the scoring model. All updates and optional sub-asset data pass through the adapter.

## Open on other devices without internet

Connect the host computer and other devices to the same trusted Wi-Fi/LAN. On the host, run:

```bash
py run.py --host 0.0.0.0 --port 8000
```

On Windows, run `ipconfig` and find the host's Wi-Fi IPv4 address. On another device, open `http://HOST-IP:8000` with that address, for example `http://192.168.1.25:8000`. Allow Python through Windows Firewall for **Private networks** if prompted. The host and server must stay running; the network does not need an internet connection. Guest Wi-Fi client isolation can prevent devices from reaching each other. This local demonstration has no login, so use a trusted network and do not expose it through router port forwarding.

## Rehearse the judging demo

For a fresh demonstration of receiving a new warning, use:

```bash
py run.py --demo-before
```

On macOS/Linux use `python3` instead of `py`. Choose **Open dashboard** on the landing page. The plant starts at **52 Elevated**. Click **Load warning** and select `examples/warning_red.json`: one new warning version is imported, ten exposed facilities are rescored, and the plant becomes **71 High**. Original files and normal saved history are preserved; this mode uses temporary in-memory history and resets when the process restarts. Import the warning before using **After warning**, then use that button for the official 06:40 export snapshot.

See [the judging demo guide](docs/DEMO_GUIDE.md) for the timed demonstration, expected results, offline proof, second-dataset run, likely questions and submission requirements. The organizers have not confirmed the demo duration in the supplied briefs.

## Try the demo

1. From the landing page, choose **Open dashboard**. The selected desalination plant starts at **71 High**, with confidence **B**.
2. Choose **Before warning** to see **52 Elevated**. Choose **After warning** to return to 71.
3. Inspect the four pillars and the top drivers: **+19.0**, **+10.3** and **+4.7** points.
4. Open **Measures**. Select the second intake, long-lead spares and three-day storage: the combined score becomes **50.2**, with **AED 725 million** capex. Scenarios never change the base facility record.
5. Open **Plans** for the supplied plan assumptions, or **History** for trends and evidence freshness.
6. Select **Before warning**, then **Load warning** and choose `examples/warning_red.json`. The file uses the starter pack's 06:30 update timestamp; the brief describes the warning arriving at 06:00. The affected facilities are rescored and recorded in the event log.
7. Use **Export scores** to download full schema-compatible JSON records. Search and sector/category filters apply to the priority list, 3D map, distribution, sector comparison and review chart; export includes the entire portfolio. The pillar chart retains the selected asset and compares it with the filtered mean.

The portfolio metrics reflect all facilities, even while the table is filtered. Each table row has its own computation time in the exported record; a warning update leaves unaffected rows untouched. The header shows the latest portfolio snapshot time.

## Push to a private GitHub repository

The download contains source files, not an existing remote repository. After extracting it, use Git and the GitHub CLI:

```bash
git init -b main
git add .
git commit -m "Build asset resilience dashboard"
gh auth login
gh repo create asset-resilience-dashboard --private --source=. --remote=origin --push
```

If Git asks for your name and email, configure your own commit identity. If you prefer GitHub's website, create an empty **private** repository and follow its instructions for pushing an existing local repository. Share only with ADCMC as directed by the brief. No remote repository has been created by this build.

GitHub Actions runs the Python tests on pushes and pull requests. The dashboard needs its Python server and is not a GitHub Pages static site.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The 45 tests cover the three formula cases, the full plant example and levers, all 120 sponsor before/after score references, missing-data behavior, monotonicity, confidence, overrides, check-up transitions, history, deterministic hashes, input validation, warning version changes, persistence, the second sample, the HTTP endpoints, frozen report snapshots, source escaping, report scope, dated input versions, per-input change effects, atomic imports and daily scheduling. A 500-facility update completed in **0.422 seconds** in the development environment; timing varies by machine.

Eighteen additional map/model/chart/report-action checks can be run with Node.js 18+ (no npm packages):

```bash
node --test tests/test_visuals.js tests/test_asset3d.js tests/test_report_actions.js
```

They check projection, all 60 model inputs, ten model families, full-turn camera framing, depth occlusion, animation lifecycle, reduced motion, supplied dependency links, selection versus dragging, keyboard controls, filtering, chart aggregates, safe text rendering, report downloads and print expansion/restoration. Node.js is optional for development and is not required to use the dashboard.

An optional real-browser smoke script is included:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
python3 -m tests.browser_smoke
```

Those optional test tools need a one-time download. They are not needed to run the dashboard. Browser rendering could not be verified in the creation environment because Chromium's required local socket was blocked. The scoring tests, map/model/chart tests, new static-asset HTTP routes and JavaScript syntax checks passed. The map and rotating asset geometry were rendered and inspected with a local software Canvas renderer. Full browser layout, WebGL rendering, and full-screen interaction remain unverified in this environment. See [validation notes](docs/VALIDATION.md).

## Another dataset

```bash
python3 run.py --data data_second_sample --db var/second.sqlite3 --population 1000000
```

Use the same six arrays: `facilities.json`, `channels.json`, `exposures.json`, `warnings.json`, `measures.json` and `plan_links.json`. Optional files are `city.json` and `score_history_pilot.json`. Field names and supplied schemas are preserved. Extra fields are retained. All input goes through `resilience/adapter.py`; there are no asset-ID branches in the scoring engine.

The second sample has no `city.json`. Supply `--population` for your own city. If omitted, the documented default is 1,000,000 and `city.population_assumed` is true. Use a separate `--db` for each dataset; a fingerprint prevents accidental mixing. This tests format portability, but the organizer's hidden dataset has not been provided or tested.

## Snapshot and daily operation

```bash
# A different historical moment
python3 run.py --at 2026-08-20T12:00:00+04:00

# Use wall time; rescore all assets when the GST date changes
python3 run.py --live

# A different port
python3 run.py --port 8080
```

The default is a frozen demonstration snapshot. In `--live` mode the running process checks the date every 30 seconds and performs a full daily run. Incoming warning files trigger immediate rescoring for exposures on both the warning's previous and new channels. Closing a risk removes it; the strongest remaining open risk on each channel takes over. Every run appends records to SQLite under `var/`; imported warnings and event logs survive restarts. The browser checks for a new snapshot every 30 seconds. The server must remain running for daily updates.

The demo replay controls deliberately select the two supplied dates, even in live mode. After using them, restart with `--live` to return to wall time. To reset the demonstration, stop the server and move or remove `var/history.sqlite3`; this removes your local run/import history. Original input files are never modified.

## Structure

| Path | Purpose |
|---|---|
| `run.py` | Local HTTP server and daily-run entry point |
| `resilience/adapter.py` | JSON loading, schema vocabulary validation, reference checks |
| `resilience/engine.py` | Pillars, score, bands, confidence, drivers, levers and sensitivity |
| `resilience/service.py` | Warning/input updates, scenarios, daily runs and SQLite history |
| `resilience/reporting.py` | Frozen HTML reports, vector charts and evidence exports |
| `scripts/` | Submission preflight and generated sample outputs |
| `web/` | HTML, CSS, app controls, offline 3D map, WebGL/software asset models, SVG charts and local icon |
| `data/`, `data_second_sample/` | Unmodified supplied synthetic inputs |
| `schemas/`, `expected/` | Unmodified sponsor schemas and reference results |
| `examples/` | Warning file and computed before/after demonstration records |
| `tests/` | Automated engine, adapter, service and API checks |
| `docs/` | Technical summary, validation notes and starter-pack readme |

## Submission preflight

On Windows, double-click **Verify_Submission.bat**, or run:

```bash
py scripts/verify_submission.py
```

This runs the Python suite and an API workflow with outbound connections denied. If Node is installed, it also runs the JavaScript checks. Results are written to `var/submission-checks.json`. Add `--browser` after installing the optional Playwright/Chromium test tools to include real-browser checks. GitHub Actions includes the same checks plus a browser job; the workflow has not run remotely until you push to your private repository.

**Start_Demo.bat** starts a fresh warning-import rehearsal. The final materials are in `docs/SUBMISSION_CHECKLIST.md`, `docs/DEMO_GUIDE.md` and the one-page `docs/TECHNICAL_SUMMARY.pdf`. A portable, generated handout and its JSON evidence are in `examples/selected_asset_report.html` and `examples/selected_asset_report_evidence.json`. The report opens without starting the app.

## Interpretation and limits

- Higher scores mean higher risk. The score is not a calibrated probability of disruption.
- Full precision is used internally. Whole-number scores use nearest-integer rounding; displayed pillars use two decimals and `score_exact` uses one, matching the sponsor's output format. Several sponsor pillar display values differ by 0.01 at floating-point boundaries; score, `score_exact`, band and confidence match all 120 reference records. Tests explicitly allow only this pillar-display tolerance.
- Warning weights follow the formula: green 0.9, unverified 1.0, amber 1.15, red 1.35. “Unverified” is not treated as less risky than green.
- A channel without an open risk is considered quiet/current for confidence, as in the reference results. Mute or blind coverage reduces confidence, never the score. The continuity return is one verified input, even if individual facts inside it are unknown; unknown recovery facts still receive zero credit.
- A full exercise is assumed within 24 months because the schema supplies no exercise date. Missing supply/population shares use the category floor; known shares are bounded to the 0–10 consequence scale.
- History starts from the supplied static facility snapshot. Dated input imports provide subsequent facility, exposure and city-population versions. Both replay and current runs include full explanations. Earlier unrecorded changes cannot be reconstructed. Pilot records remain unchanged; replay backfill is bounded to 100 days.
- Change drivers compare warning versions and individual facility inputs, exposures and population with their values at the previous-day cutoff. Named audit/control rows are matched by identity; row reordering does not create a change. Score records include all recorded input changes, including zero-effect evidence/metadata changes. Only material effects compete for the top three drivers, ranked by absolute effect. Weakness drivers evaluate best-state counterfactuals; redundancy is a joint V/R factor. Effects are not additive.
- A check-up is proposed on upward entry into High or Severe, or a 30-day rise of at least 15 points. A first-ever observation without prior history is not a band transition. A decrease from Severe to High does not independently propose a new check-up. Analyst acknowledgement remains null; this app does not implement a named-user approval workflow.
- Measure definitions without `facility_changes` are displayed as unmodeled and disabled in combined scenarios. No effectiveness is invented. Conflicting selected changes are rejected.
- A zero pillar makes the geometric score zero; the Category 1–2 override still applies. This follows the required formula rather than changing its behavior.
- The offline validator supports every validation keyword in the supplied schemas. It rejects unknown validation keywords rather than pretending to implement all of JSON Schema Draft 2020-12. A production adapter can use a full validator.
- This is a local, single-analyst demonstration. It does not include authentication, TLS, shared-user approvals or production hosting. The Python HTTP server is bound to localhost by default.

## Ownership and dependencies

The supplied brief says ADCMC owns submitted code and materials and restricts sharing. No public/open-source license is granted here for the submission or starter pack. See [OWNERSHIP.md](OWNERSHIP.md).

| Component | Use | License |
|---|---|---|
| Python standard library | Application runtime and tests | Python Software Foundation License |
| HTML, CSS, JavaScript and SVG in this repository | Application interface | Submission ownership terms |
| Playwright (optional) | Browser tests only | Apache 2.0 |
| Node.js (optional) | Map/chart/report tests only | MIT and bundled component licenses |
| ReportLab (optional) | Rebuilding the one-page submission summary only | BSD |
| `actions/checkout`, `actions/setup-python`, `actions/setup-node` | GitHub CI only | MIT |

The brief's MIT/BSD/Apache dependency condition is satisfied by having no third-party application dependencies; Python itself is the required language runtime. Review the sponsor's interpretation if language-runtime licensing is in scope.

Implementation references: [Python HTTP server](https://docs.python.org/3/library/http.server.html), [unittest](https://docs.python.org/3/library/unittest.html), and [GitHub CLI repository creation](https://cli.github.com/manual/gh_repo_create). The challenge documents and starter-pack README remain the authority for scoring.
