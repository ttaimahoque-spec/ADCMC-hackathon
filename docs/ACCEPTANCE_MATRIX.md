# Requirements and evidence

Source mapping: Challenge 01 technical brief (sections What you will build, Acceptance tests, Reuse requirements); challenge brief; mentor deck slides 3-10 and 12, with the slide 10 implementation notes. Optional predictive ML and Arabic/RTL are outside the completed mandatory scope.

| Requirement | Evidence in this project | State |
|---|---|---|
| T/V/R/C and whole-number score | `tests/test_engine.py`; pure formula functions | Passed supplied cases |
| 52 to 71; B confidence; drivers and levers | Worked-example test and `examples/scores_*.json` | Passed |
| Reference portfolio results | 120 before/after score, band, confidence references | Passed; pillar displays tolerate 0.01 |
| Category 1-2 override | Override and boundary tests | Passed |
| Conservative unknown inputs | Vulnerability/recovery and threat-confidence tests | Passed |
| Monotonic danger; independent confidence | Engine tests | Passed |
| Ranked list, sector/category filters, facility cards | Existing dashboard and browser smoke script | Implemented; full browser check pending |
| Warning update for 500 within 60 seconds | Benchmark plus unchanged-unexposed-record test | Passed in 0.422 seconds here |
| Full daily run | `Service.daily_tick` and day-boundary test; `--live` loop | Passed simulated clock boundary |
| Drivers for changes since yesterday | Individual-input counterfactuals; identity matching for audit/control rows | Passed audit, control, continuity, consequence, exposure, population, metadata and membership cases |
| Dated input history and replay | Atomic input updates, replay and restart tests | Passed |
| Trends and check-up transitions | 7/30/90-day history and exact-transition tests | Passed |
| Named human authority | Check-up proposal only; no automatic intervention | Implemented; named-user acknowledgment remains null |
| Ranking changes at +/-20% weights | Six normalized scenarios and generated results | Implemented and tested |
| One shared input adapter | Required JSON and optional sub-assets loaded/validated in adapter; updates validated there | Passed boundary tests |
| Schema-compatible output | Score validator on generated records and imports | Passed supplied schema vocabulary |
| Traceability | Timestamp, gen0-1.1.0, input hash, prior-day context, recorded changes | Tested |
| Second city without scoring-code changes | 12-facility sample via adapter and alternate-city path | Passed |
| No hard-coded score outputs | All values calculated by engine; default demo selections have fallbacks | Implemented |
| Offline execution | 22 HTTP requests while outbound connections denied; report resources embedded | Passed API check; laptop/browser proof pending |
| One-command run | `py run.py` / `python3 run.py`; no application package install | Implemented |
| Permissive dependencies | No third-party application libraries; runtime/test licenses listed in README | Documented; Python runtime has PSF license |
| One-page technical summary and AI disclosure | `docs/TECHNICAL_SUMMARY.pdf` | Generated and one-page checked |
| Demo | Fresh baseline, supplied warning, three-minute walkthrough and launch script | Prepared for live demonstration; no recorded video |
| Private repository/reviewer access | README and submission checklist; CI included | User account step, not pushed |
| Hidden organizer dataset | Not provided | Not tested |
| Optional Arabic/RTL and ML challenger | Not implemented | Optional, not claimed |
| Report export and 3D visuals | Portable HTML, SVG figures, PDF print layout, interactive illustrative models | Extra features; browser/print validation pending |

Historical facts before an explicit input update come from the supplied static baseline. Zero-effect metadata changes are recorded but do not compete with material top-three score drivers. Warning versions remain a joint risk-change factor, preserving the sponsor's +19.0 example. Effects are separate counterfactuals, not additive.

The brief's exercise-age requirement cannot be independently checked when the source supplies only `exercise: full` with no exercise date. That assumption remains disclosed; no date was invented. The data and models remain fictional.
