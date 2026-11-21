# Submission handoff

Version: gen0-1.1.0. Reviewed against both supplied briefs and the 12-slide mentor presentation, including speaker notes, on 17 November 2026 (GST).

## Prepared in this package

| Deliverable | Location |
|---|---|
| Source code and one-command README | Project root; `py run.py` or `python3 run.py` |
| Fresh live-demo launch | `Start_Demo.bat` or `py run.py --demo-before` |
| One-page technical summary | `docs/TECHNICAL_SUMMARY.pdf` (editable source beside it) |
| Automated checks | `tests/`; `Verify_Submission.bat`; `scripts/verify_submission.py` |
| Official demo outputs | `examples/scores_before.json`, `examples/scores_after.json` |
| Sensitivity evidence | `examples/ranking_sensitivity.json` |
| Portable report and complete evidence | `examples/selected_asset_report.html` and matching `_evidence.json` |
| Demo script and judge Q&A | `docs/DEMO_GUIDE.md` |
| Requirements and evidence mapping | `docs/ACCEPTANCE_MATRIX.md` |
| Private-repository CI | `.github/workflows/tests.yml` |

The illustrative 3D assets, landing page, dashboard and reports remain part of the submission. No public deployment is needed.

## Steps requiring your computer or account

1. Extract the new package into a new folder. Run **Verify_Submission.bat** (or `py scripts/verify_submission.py`) and retain `var/submission-checks.json` as local validation evidence. Node checks are optional if Node is absent; CI includes them.
2. Rehearse the supplied scenario on the actual presentation laptop with internet switched off. Start with **Start_Demo.bat**, open the landing page, enter the dashboard, load `examples/warning_red.json`, show 52 to 71, select the three measures and show 50.2. Check rotation, filters, plans, history and report downloads. Use Print / Save as PDF and inspect pagination.
3. Choose the permitted demo format: perform the live walkthrough using `docs/DEMO_GUIDE.md`, or record that walkthrough as a short video with your own narration. The organizer has not confirmed the duration in the supplied documents. No video is claimed to have been recorded in this package.
4. Create or update your **private** GitHub repository. Put `run.py` and `README.md` at its root and upload the extracted project contents, including `.github` and `.gitignore`. Exclude `var/`, local databases, caches and credentials. The ZIP already excludes runtime history and credentials. Keep the repository private.
5. Invite only the reviewer accounts explicitly supplied by ADCMC. A repository URL alone does not grant access. Confirm their access/invitation acceptance before submitting.
6. Check GitHub Actions after the push. It runs Python, JavaScript, outbound-denied API and browser tests. These jobs are prepared but have not run on a remote repository in this environment.
7. Follow the organizers' final submission instructions, supplying the repository URL, live-demo/video arrangements, one-page PDF summary, outputs and tests. The written brief names 20 November 2026 and AI@adcmc.gov.ae; the slide deck leaves dates/method unconfirmed. Confirm the final deadline time, demo duration and reviewer accounts.

GitHub integration was declined for this request, so the package has not been pushed and no reviewer invitations or submission emails have been sent. Do not make the repository or demo public.

## Verification boundaries

The numerical, data, API and visual-logic checks passed locally. Chromium is blocked by the build environment's required local socket, so browser/WebGL interaction and report print pagination remain unverified here. The laptop rehearsal and optional browser test are the remaining local proof. The organizer's hidden dataset cannot be tested before it is supplied. Neither the one-page summary nor this checklist claims prize eligibility or a placing.
