# Challenge 01 — Asset Resilience Score: starter pack

Everything here is synthetic. Madinat Al Sahil and every facility, person and number in it are made up. Read this file first, then the technical brief.

**Challenge window:** Thursday 12 November 2026 to Friday 27 November 2026, 23:59 UAE time (GST, UTC+4).

## What is in the pack

| Path | What it holds |
| --- | --- |
| `briefs/` | The two-page challenge brief and the technical brief, with the current dates |
| `data/city.json` | City facts: population (1,000,000, needed for pillar C), time zone and the dates of the warning log |
| `data/facilities.json` | 60 facilities across the nine sectors, including the desalination plant `AST-0001` exactly as in the worked example |
| `data/channels.json` | The 12 threat channels |
| `data/exposures.json` | The exposure matrix: one record per facility and channel (720 records), each signed by a named analyst |
| `data/warnings.json` | The 90-day warning log (day 1 = 2026-06-02, day 87 = 2026-08-27, day 90 = 2026-08-30) |
| `data/plan_links.json` | Which city plans rely on which facilities; use it for `dependent_plans` |
| `data/measures.json` | Costed measures; their `facility_changes` are your levers |
| `data/sub_assets.json` | The plant's internal parts (used in Challenge 03; here for reference) |
| `data/score_history_pilot.json` | Scores from the sponsor's pilot for 29 May to 1 June 2026, so 90-day trends work up to the end of the log |
| `schemas/` | JSON Schemas for every record, including the `score` record you produce |
| `samples/score_AST-0001_2026-08-27T0640.json` | The plant's score record at 06:40 on day 87 |
| `expected/worked_example.json` | Every number in the worked example, for your tests |
| `expected/formula_tests.json` | The three formula tests |
| `expected/all_facilities_day87.json` | Reference pillars, score, band and confidence for all 60 facilities, the evening before and after the warning |
| `data_second_sample/` | A small second city (12 facilities) in the same formats. Use it to prove your adapter loads a second dataset with no change to core code |

The hidden test dataset used for judging is **not** included. It uses the same formats with different facilities and events, so do not hard-code anything about this city.

## How to read the data

**Warnings are a log of versions.** Each row is one version of a risk. The current state of a risk at time *t* is its latest row with `updated_at` at or before *t*. A row with `status: "closed"` means the risk no longer applies. `status` is a starter-pack addition to the warning format.

**Live risk per channel.** A warning applies to every channel in its `channels` list. For each exposed channel, use the open risk with the highest p̂, as the brief says.

**Controls.** `state` is one of `absent` (10), `present_untested` (8), `tested_stale` (5) or `tested_current` (1). `null` means unknown (10).

**Confidence: the required inputs.** For each facility, count:
- its `status`;
- its `continuity` block;
- each audit domain;
- each control;
- each exposed channel.

An input is current when:
- it is known;
- it was verified within the `cadence_days` in its `provenance` entry, measured from `last_verified`, or from `assessed_at` / `verified_at` for audit domains and controls;
- for a channel: the strongest live warning on it does not have `coverage` of `mute` or `blind`.

The plant has 12 required inputs and 10 are current, giving grade B.

**Trends.** A trend compares today's score with the most recent stored score at or before the same time 7, 30 or 90 days earlier. Put the pilot history file into your history store before replaying the log.

**Measures and levers.** `facility_changes` use field paths into the facility record. Two forms are used:
- dotted fields, such as `continuity.spares_on_site`;
- a named control, such as `controls[name=algal monitoring].state`.

A lever is the score with those changes applied.

## Check yourself

Your engine is on track when, for `AST-0001`:
- the evening before (2026-08-26 20:00) gives 51.9 → 52 Elevated;
- 06:40 on 2026-08-27 gives 70.9 → 71 High, confidence B;
- the drivers are +19.0, +10.3 and +4.7;
- the levers are 60.5, 66.2, 67.8 and 69.4, and 50.2 with the first three together.

Everything else in `expected/` should also match.

## Rules (from the brief)

- **Synthetic data only.** Do not add real facility names or coordinates.
- **Numbers come from code.**
- **Do not share the pack or your work outside ADCMC.**

## What is not in the pack

- **Your own tools.** Use any programming language and libraries, as long as dependencies are under MIT, BSD or Apache 2.0 licences. Python 3 is the common choice.
- **The hidden test set.** The organisers keep it for judging.
- **Mentor contact and submission method.** These are in the Key details table of your two-page brief (in `briefs/`).

## Questions

If something in the pack looks wrong or unclear, ask your ADCMC mentor before working around it.
