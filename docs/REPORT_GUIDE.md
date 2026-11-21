# Landing page and reports

The app opens on a separate landing page at `/`. Choose **Open dashboard** to enter `/dashboard`. The model is illustrative and uses the same local renderer as the dashboard. No internet connection is needed.

## Produce the report

1. Run `py run.py --demo-before`, open `http://127.0.0.1:8000`, and enter the dashboard.
2. Load `examples/warning_red.json`. Select **After warning** for the official 06:40 snapshot.
3. Select **Al Sahil Desalination Plant**, open **Measures**, and check second intake, long-lead spares and three-day storage. Confirm **50.2**, **AED 725,000,000 capex**, and **AED 7,000,000 annual opex**.
4. Click **Create report**. The full report opens in a new tab. It includes every facility regardless of dashboard filters, and preserves the selected scenario.
5. For a shorter handout, choose **Create a shorter selected-asset report**. This creates a new report at the current server snapshot and keeps the same selected measures.
6. Choose **Download HTML report** to save one portable file. Choose **Print / Save as PDF** to open the browser's print dialog and save a PDF. Choose **Download evidence JSON** for structured evidence.

## What is included

| Section | Contents |
|---|---|
| Cover | City, scope, portfolio snapshot, generation time, selected asset, snapshot hash |
| Portfolio analysis | Band counts, sector averages, score versus consequence, print-friendly coordinate/dependency map |
| Asset register | Every asset, priority rank, sector, category, published/exact score, band, confidence, check-up state |
| Asset dossiers | Four-pillar graph, drivers, individual measures, costs, plan assumptions, history graph/table, evidence freshness, input hash and model version |
| Source evidence | Every facility field, audits, controls, continuity facts, provenance, exposures, sub-assets, full plan links, measure lifetimes and modeled input changes |
| Selected scenario | Selected measures, joint score/band/pillars, reduction, capex and annual opex |
| Warning evidence | Open warnings, full version log through the snapshot, channels, import events |
| Methodology | Formula, bands/overrides, confidence rules, sensitivity results/rank movements, assumptions and city metadata |

The full report includes all dossiers. The shorter version includes only the selected dossier but still contains full portfolio charts and the complete asset register. The embedded/downloadable JSON retains the complete portfolio evidence in either case.

The map is a static plan view using supplied local coordinates, not a screenshot of the rotating viewer. The 3D models are not surveyed geometry and are not used as evidence. Graphs are embedded SVG vectors, so they remain sharp in a PDF.

## Check the downloaded report

- Open the saved HTML file after stopping the app. The report, charts, print button and evidence download should still work. Navigation back to the app is hidden in file mode.
- Review the first pages in print preview. Use A4, normal scale and a PDF destination. Page counters may vary by browser; disable duplicate browser headers/footers if needed.
- Confirm the source timestamp and asset computation times are present. The generation time is UTC, while input timestamps keep their explicit offsets.
- Confirm the selected scenario uses the engine output and exact costs. No measures selected is explicitly stated when applicable.
- Verify the Arabic facility name, long plan assumptions and input hash are legible. Full source/history tables can span many pages; table headers repeat.
- Save the HTML or JSON as well as the PDF when machine-readable evidence is required. A PDF has no embedded JSON attachment.

## Validation boundary

Automated tests check snapshot integrity, read-only generation, complete dossier coverage, selected scope, second sample, escaping, Unicode, warning/history cutoffs, costed scenarios, routes, script policy, download actions and print expansion. SVG charts were rendered and visually inspected. Full browser layout and PDF pagination could not be executed in the creation environment because Chromium's local socket was blocked. Run `tests/browser_smoke.py` on a development machine with Playwright and Chromium installed, and rehearse printing on the presentation laptop.


Dated source updates
-------------------

After loading a dated asset-input update, reports include its source records, per-input change effects and import event. A report at an earlier replay date excludes later input versions. Optional sub-assets are loaded and validated through the same adapter as other source records. The prepared `examples/selected_asset_report.html` uses the original official snapshot and the three-measure scenario.
