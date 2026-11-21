# Sahil Atlas — judging demo guide

Reviewed against the supplied Challenge 01 technical brief and challenge brief on 15 November 2026 (GST). The stated submission deadline is 20 November 2026, by email to AI@adcmc.gov.ae. The video/live-demo duration and judging weights remain subject to organizer confirmation. The three-minute sequence below is a rehearsal plan, not an organizer-imposed limit.

## What the judges need to see

The entry must pass every acceptance test before it is eligible. The provisional rubric is technical functionality 30%, problem-solving/solution quality 25%, innovation/added value 15%, usability/demonstration 15%, and code quality/documentation 15%. A strong demonstration connects an incoming warning to an explainable score, a human review, and costed ways to improve resilience. The 3D model supports orientation; numerical evidence and a reproducible workflow carry the main story.

## Start a fresh, repeatable demonstration

Extract the latest project to a new folder and stop any old server. Open a terminal in the directory containing `run.py` and run:

```bash
# Windows
py run.py --demo-before

# macOS / Linux
python3 run.py --demo-before
```

Open http://127.0.0.1:8000 and choose **Open dashboard**. Allow history reconstruction to finish. The plant starts at 52 Elevated. This mode uses the supplied records up to the baseline date and holds future warning versions out of memory. Loading `examples/warning_red.json` therefore imports one new version and updates ten exposed facilities. Source files and the normal saved database remain unchanged. Stopping the process discards this rehearsal's history; restarting the same command gives a fresh baseline.

Do not press **After warning** before importing the warning in this mode. It is a fresh ingestion demonstration, so that future version has not been loaded yet. For the ordinary complete historical replay, use `py run.py` without the flag.

## Three-minute core demonstration

| Time | Action | Point to make |
|---|---|---|
| 0:00–0:15 | Show the plant at 52 Elevated and the 60-facility overview. | A coastal city depends on a plant with one intake and about one day of stored water. The analyst needs to decide what deserves attention first. Higher scores mean higher risk. |
| 0:15–0:30 | Briefly rotate the plant model and show its map/dependency links. | Models are illustrative. Coordinates and relationships come from the supplied fictional data. Keep this visual introduction short. |
| 0:30–0:55 | Click **Load warning**, choose `examples/warning_red.json`, and show the change to 71 High. Open **Warning feed** briefly to show one new version, ten affected facilities and measured elapsed time. Return to the overview. | This is an actual local warning import with selective rescoring. The untouched facilities retain their previous score records. The elapsed time here is for ten facilities; the separate automated benchmark covers 500. |
| 0:55–1:20 | Show the four pillars, confidence B and top three drivers. | T 5.58, V 6.50, R 6.94, C 10.00. Drivers: warning +19.0, single point of failure +10.3, missing spares +4.7. Confidence B means 10 of 12 inputs current; it does not reduce the risk score. Driver effects are separate counterfactuals and are not added together. |
| 1:20–1:50 | Open **Measures**. Show the individual results, then select second intake, long-lead spares and three-day storage. | Individual scores are 60.5, 66.2 and 67.8. Their recomputed combined scenario is 50.2, with AED 725 million capex and AED 7 million annual opex. These are synthetic planning inputs, not a real investment recommendation. |
| 1:50–2:15 | Open **Plans** and point to `PLN-WTR-001`, section 3.2. Then return to Overview and the check-up proposal. | The supplied plan assumes a second intake can carry the load, while the plant record describes a single intake. Bringing these records together helps an analyst identify what to examine. The app displays the assumption; it does not automatically verify the plan. A human decides whether and how to proceed with a check-up. |
| 2:15–2:35 | Open **History**; then show sector/category filtering in the ranked list. | The supplied history supports +19 over 7, 30 and 90 days for the plant. The analyst can inspect the wider portfolio and evidence freshness. |
| 2:35–2:50 | Open **Scoring methodology**, briefly show the formula and ranking sensitivity. | The model is deterministic and follows the prescribed formula. The required ±20% vulnerability-weight analysis reports how rankings change. |
| 2:50–3:00 | Return to the overview. Choose **After warning** for the official 06:40 snapshot and **Export scores**. | Outputs preserve the required schema, including time, model version and inputs hash, ready for reuse by the sister projects. |

The narrative brief describes a 06:00 warning; the supplied warning file is timestamped 06:30. The target output is 06:40. Use the supplied file unchanged and distinguish these times if asked. Clicking After warning after the import produces the official 06:40 snapshot; the import itself evaluates at the file's 06:30 time.

## Technical evidence to have ready

Run these before recording. Keep the output available for questions rather than spending the main presentation reading test names.

```bash
py -m unittest discover -s tests -v
node --test tests/test_visuals.js tests/test_asset3d.js tests/test_report_actions.js
```

Node.js is optional for development tests; the dashboard itself only needs Python and a browser. The Python suite covers the formula cases, worked example, sponsor portfolio references, conservative unknown-data handling, overrides, confidence independence, deterministic hashes, history, warning ingestion, 500-facility timing, second sample, persistence, HTTP behavior and the fresh demo mode.

Have a second instance prepared on another port to show the adapter loading a different supplied dataset without core-code edits:

```bash
py run.py --data data_second_sample --db var/second-demo.sqlite3 --population 1000000 --port 8001
```

Open http://127.0.0.1:8001 and show 12 facilities. This supports portability; it does not prove that the organizer's unseen dataset will pass.

For the offline check, turn off Wi-Fi/internet access on the presentation laptop, restart the app locally, reload the page, rotate the model and import the warning. The localhost workflow works without Wi-Fi. Use this test on the actual presentation machine: full browser/WebGL validation was blocked in the build environment.

If using the optional browser test, install Playwright and Chromium in advance while online, then run `py -m tests.browser_smoke`. These test dependencies are not required by the app.

## Answers to likely questions

- **Is 71 a 71% probability of failure?** No. It is the required 0–100 prioritization score. The app does not provide a calibrated disruption probability.
- **Are the building models real digital twins?** They are illustrative meshes selected from asset metadata. Actual geometry, temperatures, damage and component states are not inferred.
- **Where is the AI?** AI coding assistance supported implementation and testing. Every score and scenario is calculated by deterministic code from supplied inputs. The brief explicitly permits this approach; the ML challenger is optional and has separate validation requirements.
- **Does the app authorize interventions?** It proposes a check-up and shows evidence. Human authorization remains outside this local demonstration; no named-user acknowledgement workflow is implemented.
- **Can it explain every historical facility edit?** It explains warning-version changes and structural weaknesses. The starter pack has no versioned facility-edit feed, so historical facility-change attribution is a documented limitation.
- **Why trust missing data?** Unknown vulnerability and recovery values receive conservative treatment. Input freshness affects confidence separately. Tests cover these rules.
- **Can the sponsor reuse it?** Fixed schemas, a single adapter, offline execution, a one-command start, traceable outputs, tests and documentation support reuse. The supplied second sample loads without changes to the core engine.

## Finish the submission

1. Complete a real offline end-to-end rehearsal on the laptop that will present. Verify warning import, models, measures, plans, export and readable text at recording resolution.
2. Keep the repository private and share only with the ADCMC reviewer accounts confirmed by the organizers. The email address is the stated submission destination; it is not evidence of a GitHub account to invite.
3. Include the source, README, automated tests and before/after output records. Include the video/live-demo material as instructed.
4. Submit a technical summary rendered to **one page at most**, covering approach, assumptions, limitations and AI use. The supplied Markdown is source material; check its pagination when exporting or printing.
5. Confirm the video duration, reviewer usernames and deadline time/timezone with the organizers; those details are not all settled in the supplied briefs.

Once the required behavior is verified, Arabic/RTL from a translation file is the most directly brief-aligned UI stretch goal. A machine-learning challenger should only be included if it meets the brief's held-out skill, calibration and ranking-stability tests. Placement cannot be predicted without the other entries and final judging.


## Landing page and report handoff

The root address now opens the landing page. At the start of a demo, spend at most five seconds on it, then choose **Open dashboard**. All scoring and warning-replay steps remain the same.

At the end, leave the plant selected with the three measures checked, then choose **Create report**. The preview includes the actual 50.2 combined scenario and exact AED costs, alongside portfolio graphs and evidence. Use **Create a shorter selected-asset report** for a manageable handout, then **Print / Save as PDF**. Download the complete HTML report and evidence JSON separately for the full evidence package. This can replace part of the final export segment rather than lengthening the core demonstration.

Say: “This report preserves the snapshot behind the decision: graphs, inputs, assumptions, costs and an audit trail. It opens without the app, and the baseline records stay unchanged.”

Practice printing on the presentation laptop before recording. The complete report includes all 60 dossiers and long source/history tables; use the shorter option during the live demonstration.


## New compliance evidence

The dashboard design is retained. The package now includes a rendered one-page `docs/TECHNICAL_SUMMARY.pdf`, an acceptance matrix and a submission checklist. Double-click `Verify_Submission.bat` to run the numerical/API checks before rehearsing.

If a judge asks whether changing facility facts are supported, demonstrate this after the main 52-to-71 workflow: select the plant, open **Warning feed**, choose **Load asset inputs**, and select `examples/input_update_spares.json`. The source update is dated 28 August 2026 and records that spares are available. The plant's exact score becomes 66.2. Open **History** and expand **Changes to source inputs** to show the previous/current value and its effect. Replay **After warning** to return to the original 27 August inputs and 71 score. Explain that importing a source record does not perform an operational intervention.

Use this only for Q&A or a longer demonstration; the three-minute core should remain focused. Model `gen0-1.1.0` includes dated changes for audit/control/recovery/consequence/exposure/population inputs, full history explanations and tested daily scheduling. No forecast or Arabic stretch goal is claimed.
