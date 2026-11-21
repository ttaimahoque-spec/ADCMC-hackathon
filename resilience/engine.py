"""Pure scoring functions. No network, clock reads, or learned parameters."""
import copy
import hashlib
import math
import re
from datetime import timedelta
from . import MODEL_VERSION
from .adapter import canonical, timestamp

HORIZON = {"H1": 1., "H2": .5, "H3": .2}
WARNING = {"green": .9, "unverified": 1., "amber": 1.15, "red": 1.35}
VELOCITY = {"fast": 1., "moderate": .75, "slow": .5}
CONTROL = {"absent": 10., "present_untested": 8., "tested_stale": 5., "tested_current": 1., None: 10.}
IRREPLACEABILITY = {"single": 10., "partial": 6., "redundant": 3.5, None: 10.}
BANDS = ["Low", "Guarded", "Elevated", "High", "Severe"]
WEIGHTS = (.4, .3, .3)


def p_hat(warning):
    return min(1., warning["likelihood"] * HORIZON[warning["horizon"]] *
               WARNING[warning["warning_level"]] * (.85 + .30 * VELOCITY[warning["velocity"]]))


def warning_state(log, at, include_closed=False):
    now, latest = timestamp(at), {}
    for row in sorted(log, key=lambda w: (timestamp(w["updated_at"]), w["risk_id"])):
        if timestamp(row["updated_at"]) <= now:
            latest[row["risk_id"]] = row
    return {key: row for key, row in latest.items() if include_closed or row.get("status", "open") != "closed"}


def channel_risks(warnings):
    strongest = {}
    for risk in sorted(warnings.values(), key=lambda w: w["risk_id"]):
        for channel in risk["channels"]:
            if channel not in strongest or p_hat(risk) > p_hat(strongest[channel]):
                strongest[channel] = risk
    return strongest


def mean(values, fallback):
    return sum(values) / len(values) if values else fallback


def pillars(facility, exposures, warnings, population, weights=WEIGHTS):
    strongest = channel_risks(warnings)
    risks = [p_hat(strongest[e["channel_id"]]) for e in exposures
             if e["exposed"] and e["channel_id"] in strongest]
    threat = 10 * (1 - math.prod(1 - p for p in risks))
    audit = mean([a["score"] if a["score"] is not None else 10 for a in facility["audit_domains"]], 10)
    controls = mean([CONTROL[c["state"]] for c in facility["controls"]], 10)
    values = [audit, controls, IRREPLACEABILITY[facility["irreplaceability"]]]
    vulnerability = sum(w * v for w, v in zip(weights, values)) / sum(weights)
    c = facility["continuity"]
    buffer = min(1, max(0, c["buffer_hours"] / c["buffer_target_hours"])) if c["buffer_hours"] is not None and c["buffer_target_hours"] is not None and c["buffer_target_hours"] > 0 else 0
    rto = int(c["rto_hours"] is not None and c["mtd_hours"] is not None and 0 <= c["rto_hours"] <= c["mtd_hours"])
    facts = [int(c["n1_redundant"] is True), buffer, rto, int(c["spares_on_site"] is True),
             int(c["plan_current"] is True), {"full": 1., "tabletop": .5}.get(c["exercise"], 0.)]
    recovery = 10 * (1 - sum(facts) / 6)
    consequence = max(12 - 2 * facility["category"], 10 * (facility["share_of_city_supply"] or 0),
                      10 * min(1, (facility["people_served"] or 0) / population))
    return dict(T=threat, V=vulnerability, R=recovery, C=consequence)


def score_value(p):
    return 100 * (math.prod(p[k] for k in "TVRC") / 10_000) ** .25


def band_for(score, p, category):
    band = BANDS[min(4, max(0, score // 20))]
    override = category <= 2 and max(p[k] for k in "TVR") >= 9 and band in BANDS[:3]
    return ("High" if override else band), override


def confidence(facility, exposures, warnings, at):
    now = timestamp(at)
    provenance = facility["provenance"]
    evidence = []

    def add(label, known, group, date=None):
        source = provenance.get(group, {})
        verified = date if date is not None else source.get("last_verified")
        current = False
        if known and verified and source.get("cadence_days"):
            age = (now - timestamp(verified)).total_seconds() / 86400
            current = 0 <= age <= source["cadence_days"]
        evidence.append({"input": label, "current": current,
                         "reason": "Current" if current else "Unknown, unverified, future-dated or outside cadence"})

    add("Operating status", facility["status"] != "unknown", "status")
    # The starter pack treats continuity as one verified block, including explicit unknown facts.
    add("Continuity return", bool(facility["continuity"]), "continuity")
    for item in facility["audit_domains"]:
        add("Audit: " + item["domain"], item["score"] is not None and item["assessed_at"] is not None,
            "audit_domains", item["assessed_at"])
    for item in facility["controls"]:
        add("Control: " + item["name"], item["state"] is not None and item["verified_at"] is not None,
            "controls", item["verified_at"])
    strongest = channel_risks(warnings)
    for exp in sorted(exposures, key=lambda e: e["channel_id"]):
        if exp["exposed"]:
            risk = strongest.get(exp["channel_id"])
            # Sponsor references count a channel with no open risk as quiet/current.
            current = risk is None or risk["coverage"] == "live"
            evidence.append({"input": f"Channel {exp['channel_id']}", "current": current,
                             "reason": "No open risk" if risk is None else "Coverage: " + risk["coverage"]})
    current = sum(e["current"] for e in evidence)
    ratio = current / len(evidence) if evidence else 0
    grade = "A" if ratio >= .9 else "B" if ratio >= .75 else "C" if ratio >= .5 else "D"
    return {"grade": grade, "current": current, "required": len(evidence), "evidence": evidence}


def apply_changes(facility, changes):
    result = copy.deepcopy(facility)
    for path, value in changes.items():
        match = re.fullmatch(r"controls\[name=(.+)\]\.state", path)
        if match:
            control = next((c for c in result["controls"] if c["name"] == match[1]), None)
            if control is None:
                raise ValueError(f"Measure references missing control: {match[1]}")
            control["state"] = value
            continue
        parts = path.split(".")
        parent = result
        for part in parts[:-1]:
            if part not in parent or not isinstance(parent[part], dict):
                raise ValueError(f"Invalid measure path: {path}")
            parent = parent[part]
        if parts[-1] not in parent:
            raise ValueError(f"Invalid measure path: {path}")
        parent[parts[-1]] = value
    return result


def checkup(band, previous_band, delta30):
    entered = band in ("High", "Severe") and previous_band is not None and BANDS.index(band) > BANDS.index(previous_band)
    return entered or (delta30 is not None and delta30 >= 15)


def history_at(history, at):
    cutoff = timestamp(at) if isinstance(at, str) else at
    candidates = [r for r in history if timestamp(r["computed_at"]) <= cutoff]
    return max(candidates, key=lambda r: timestamp(r["computed_at"]), default=None)


def input_change_candidates(facility, exposures, warnings, population, previous):
    """One-input counterfactuals against dated facts at the previous-day cutoff.

    Named audit/control rows are matched by identity, so reordering does not
    invent a change. Added/removed rows restore their earlier membership.
    Zero-effect changes stay in the audit list, but are not top score drivers.
    """
    if previous is None:
        return []
    base = score_value(pillars(facility, exposures, warnings, population))
    old = previous["facility"]
    changes = []

    def add(name, before, after, changed=None, exps=None, pop=None):
        effect = base - score_value(pillars(facility if changed is None else changed,
                                            exposures if exps is None else exps, warnings,
                                            population if pop is None else pop))
        changes.append({"factor": name, "kind": "change", "effect": round(effect, 1),
                        "previous": before, "current": after, "_effect": abs(effect)})

    for key in sorted(set(facility) | set(old)):
        if key in ("audit_domains", "controls", "continuity"):
            continue
        if canonical(facility.get(key)) == canonical(old.get(key)):
            continue
        changed = copy.deepcopy(facility)
        if key in old:
            changed[key] = copy.deepcopy(old[key])
        else:
            changed.pop(key, None)
        add("Facility: " + key.replace("_", " ") + " changed", old.get(key), facility.get(key), changed)
    for key in sorted(set(facility["continuity"]) | set(old["continuity"])):
        before, after = old["continuity"].get(key), facility["continuity"].get(key)
        if canonical(before) == canonical(after):
            continue
        changed = copy.deepcopy(facility)
        if key in old["continuity"]:
            changed["continuity"][key] = before
        else:
            changed["continuity"].pop(key, None)
        add("Continuity: " + key.replace("_", " ") + " changed", before, after, changed)
    for group, identity in (("audit_domains", "domain"), ("controls", "name")):
        before_rows = {v[identity]: v for v in old[group]}
        after_rows = {v[identity]: v for v in facility[group]}
        for name in sorted(set(before_rows) | set(after_rows)):
            before, after = before_rows.get(name), after_rows.get(name)
            if before == after:
                continue
            # Compare each changed numeric input separately; metadata changes
            # are recorded too, even when they affect confidence only.
            keys = sorted((set(before) | set(after)) - {identity}) if before is not None and after is not None else [None]
            for key in keys:
                b, a = (before.get(key), after.get(key)) if key else (before, after)
                if b == a:
                    continue
                changed = copy.deepcopy(facility)
                if key:
                    row = next(v for v in changed[group] if v[identity] == name)
                    if key in before:
                        row[key] = copy.deepcopy(b)
                    else:
                        row.pop(key, None)
                else:
                    changed[group] = [v for v in changed[group] if v[identity] != name]
                    if before is not None:
                        changed[group].append(copy.deepcopy(before))
                add(f'{"Audit" if group == "audit_domains" else "Control"}: {name}' + (f' / {key}' if key else '') + ' changed', b, a, changed)
    before_exps = {e["channel_id"]: e for e in previous["exposures"]}
    after_exps = {e["channel_id"]: e for e in exposures}
    for channel in sorted(set(before_exps) | set(after_exps)):
        before, after = before_exps.get(channel), after_exps.get(channel)
        if before == after:
            continue
        changed = [e for e in exposures if e["channel_id"] != channel]
        if before is not None:
            changed.append(before)
        add(f"Exposure: channel {channel} changed", before, after, exps=changed)
    if population != previous["population"]:
        add("City population changed", previous["population"], population, pop=previous["population"])
    return changes


def explain(facility, exposures, warnings, yesterday, population, measures, input_changes=()):
    base = score_value(pillars(facility, exposures, warnings, population))
    candidates = [dict(c) for c in input_changes if c["_effect"] > .00001]

    def weakness(label, changed):
        effect = base - score_value(pillars(changed, exposures, warnings, population))
        if effect > .00001:
            candidates.append({"factor": label, "kind": "weakness", "effect": round(effect, 1), "_effect": effect})

    exposed = {e["channel_id"] for e in exposures if e["exposed"]}
    for key in sorted(set(warnings) | set(yesterday)):
        today, old = warnings.get(key), yesterday.get(key)
        if today == old or not exposed.intersection((today or {}).get("channels", []) + (old or {}).get("channels", [])):
            continue
        counterfactual = dict(warnings)
        if old is None:
            counterfactual.pop(key, None)
        else:
            counterfactual[key] = old
        effect = base - score_value(pillars(facility, exposures, counterfactual, population))
        if abs(effect) > .00001:
            candidates.append({"factor": (today or old)["title"], "kind": "change", "effect": round(effect, 1), "_effect": abs(effect)})
    weakness("Single point of failure" if facility["irreplaceability"] == "single" else "Limited redundancy",
             apply_changes(facility, {"irreplaceability": "redundant", "continuity.n1_redundant": True}))
    for label, changes in [
        ("No long-lead spares on site", {"continuity.spares_on_site": True}),
        ("Recovery time exceeds tolerable disruption", {"continuity.rto_hours": 0, "continuity.mtd_hours": max(0, facility["continuity"]["mtd_hours"] or 0)}),
        ("Buffer below target", {"continuity.buffer_hours": 1, "continuity.buffer_target_hours": 1}),
        ("Protection plan not confirmed current", {"continuity.plan_current": True}),
        ("No current full exercise", {"continuity.exercise": "full"}),
    ]:
        weakness(label, apply_changes(facility, changes))
    for i, audit in enumerate(facility["audit_domains"]):
        changed = copy.deepcopy(facility)
        changed["audit_domains"][i]["score"] = 0
        weakness("Audit weakness: " + audit["domain"].replace("_", " "), changed)
    for control in facility["controls"]:
        weakness("Control gap: " + control["name"], apply_changes(facility, {f"controls[name={control['name']}].state": "tested_current"}))
    drivers = sorted(candidates, key=lambda c: -c["_effect"])[:3]
    for driver in drivers:
        del driver["_effect"]
    levers = []
    for measure in measures:
        changed = apply_changes(facility, measure["facility_changes"])
        after = score_value(pillars(changed, exposures, warnings, population))
        levers.append({"measure": measure["name_en"], "measure_id": measure["measure_id"],
                       "score_after": round(after, 1), "reduction": round(base - after, 1),
                       "capex_aed": measure["capex_aed"], "opex_aed_per_year": measure["opex_aed_per_year"],
                       "modeled": bool(measure["facility_changes"])})
    return drivers, levers


def score_record(adapter, facility, at, history=(), explain_score=True, warning_log=None):
    log = adapter.warnings if warning_log is None else warning_log
    warnings = warning_state(log, at)
    exposures = adapter.exposure_index[facility["asset_id"]]
    population = adapter.city["population"]
    p = pillars(facility, exposures, warnings, population)
    exact = score_value(p)
    score = math.floor(exact + .5)
    band, override = band_for(score, p, facility["category"])
    conf = confidence(facility, exposures, warnings, at)
    now = timestamp(at)
    comparison_at = (now - timedelta(days=1)).isoformat()
    has_versions = any(timestamp(u["effective_at"]) <= now for u in adapter.input_updates)
    previous_inputs = adapter.inputs_for(facility["asset_id"], comparison_at) if has_versions else None
    previous = history_at(history, now - timedelta(microseconds=1))
    trend = {}
    trend_sources = {}
    for days in (7, 30, 90):
        old = history_at(history, now - timedelta(days=days))
        trend[f"d{days}"] = score - old["score"] if old else None
        trend_sources[f"d{days}"] = {k: old[k] for k in ("computed_at", "score")} if old else None
    plans = [r for r in adapter.plan_links if r["asset_id"] == facility["asset_id"]]
    measures = [m for m in adapter.measures if m["asset_id"] == facility["asset_id"]]
    drivers, levers = [], []
    input_changes = input_change_candidates(facility, exposures, warnings, population, previous_inputs)
    if explain_score:
        yesterday = warning_state(log, comparison_at)
        drivers, levers = explain(facility, exposures, warnings, yesterday, population, measures, input_changes)
    inputs = {"facility": facility, "exposures": sorted(exposures, key=lambda e: e["channel_id"]),
              "warnings": warnings, "population": population, "measures": sorted(measures, key=lambda m: m["measure_id"]),
              "plans": sorted(plans, key=canonical), "as_of": at, "weights": WEIGHTS, "version": MODEL_VERSION,
              "yesterday_warnings": warning_state(log, (now - timedelta(days=1)).isoformat()),
              "trend_sources": trend_sources, "previous_band": previous["band"] if previous else None,
              "explanations_included": explain_score}
    inputs["previous_day_inputs"] = previous_inputs
    return {"asset_id": facility["asset_id"], "computed_at": at, "score": score,
            "score_exact": round(exact, 1), "band": band, "override_applied": override,
            "confidence": conf["grade"], "confidence_inputs": conf,
            "pillars": {k: round(v, 2) for k, v in p.items()}, "drivers": drivers, "levers": levers,
            "trend": trend, "dependent_plans": sorted({p["plan_id"] for p in plans}),
            "review": {"proposed_checkup": checkup(band, previous["band"] if previous else None, trend["d30"]), "acknowledged_by": None},
            "input_changes": [{k: v for k, v in c.items() if k != "_effect"} for c in input_changes],
            "change_comparison": {"as_of": comparison_at, "dated_inputs_available": has_versions,
                                  "baseline": "Supplied static facility snapshot; explicit updates override it from their effective_at time."},
            "inputs_hash": "sha256:" + hashlib.sha256(canonical(inputs).encode()).hexdigest(), "model_version": MODEL_VERSION}


def sensitivity(adapter, at):
    warnings = warning_state(adapter.warnings, at)
    def ranked(weights):
        values = [(f["asset_id"], score_value(pillars(f, adapter.exposure_index[f["asset_id"]], warnings,
                                                    adapter.city["population"], weights))) for f in adapter.facilities]
        return {asset: i + 1 for i, (asset, _) in enumerate(sorted(values, key=lambda r: (-r[1], r[0])))}
    baseline = ranked(WEIGHTS)
    scenarios = []
    for i, label in enumerate(("Audit", "Controls", "Irreplaceability")):
        for multiplier in (.8, 1.2):
            weights = list(WEIGHTS)
            weights[i] *= multiplier
            ranks = ranked(weights)
            changes = [{"asset_id": a, "baseline": baseline[a], "rank": ranks[a], "movement": baseline[a] - ranks[a]}
                       for a in sorted(ranks, key=lambda a: (-abs(baseline[a] - ranks[a]), a))]
            scenarios.append({"label": f"{label} {'−20%' if multiplier < 1 else '+20%'}",
                              "weights": [round(w / sum(weights), 4) for w in weights],
                              "moved": sum(c["movement"] != 0 for c in changes),
                              "max_movement": max(abs(c["movement"]) for c in changes), "changes": changes})
    return scenarios
