import copy
import json
import math
import unittest
from datetime import timedelta
from unittest.mock import patch
from resilience.adapter import Adapter, ROOT, timestamp, validate
from resilience.engine import (WARNING, apply_changes, band_for, checkup, confidence, history_at,
                               p_hat, pillars, score_record, score_value, warning_state, sensitivity)
from resilience.service import BEFORE, AFTER


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = Adapter(ROOT / "data")
        cls.facility = cls.adapter.facilities[0]
        cls.expected = json.loads((ROOT / "expected/worked_example.json").read_text())

    def value(self, facility=None, warnings=None, exposures=None):
        return score_value(pillars(facility or self.facility,
                                  self.adapter.exposure_index["AST-0001"] if exposures is None else exposures,
                                  warning_state(self.adapter.warnings, AFTER) if warnings is None else warnings,
                                  self.adapter.city["population"]))

    def test_formula_cases(self):
        for case in json.loads((ROOT / "expected/formula_tests.json").read_text()):
            with self.subTest(case=case):
                p = {k: case[k] for k in "TVRC"}
                score = math.floor(score_value(p) + .5)
                self.assertEqual(score, case["score"])
                self.assertEqual(band_for(score, p, 3)[0], case["band"])

    def test_worked_example_before_and_after(self):
        for phase in ("evening_before", "after_warning"):
            want = self.expected[phase]
            r = score_record(self.adapter, self.facility, want["at"])
            for key in ("score", "score_exact", "band"):
                self.assertEqual(r[key], want[key])
            for key in "TVRC":
                self.assertEqual(r["pillars"][key], want[key])
        r = score_record(self.adapter, self.facility, AFTER)
        self.assertEqual(r["confidence"], "B")
        self.assertEqual((r["confidence_inputs"]["current"], r["confidence_inputs"]["required"]), (10, 12))
        self.assertEqual([d["effect"] for d in r["drivers"]], [19.0, 10.3, 4.7])
        self.assertEqual([d["kind"] for d in r["drivers"]], ["change", "weakness", "weakness"])
        self.assertFalse(r["override_applied"])

    def test_warning_probabilities(self):
        before, after = warning_state(self.adapter.warnings, BEFORE), warning_state(self.adapter.warnings, AFTER)
        self.assertEqual(round(p_hat(before["RSK-BLOOM-001"]),4), .0726)
        self.assertEqual(p_hat(before["RSK-HEAT-001"]), .0945)
        self.assertEqual(round(p_hat(after["RSK-BLOOM-001"]),3), .512)

    def test_every_reference_score_band_and_confidence(self):
        reference = json.loads((ROOT / "expected/all_facilities_day87.json").read_text())
        for phase in ("evening_before", "after_warning"):
            for want in reference[phase]:
                with self.subTest(phase=phase, asset=want["asset_id"]):
                    actual = score_record(self.adapter, self.adapter.by_id[want["asset_id"]], want["computed_at"])
                    for key in ("score", "score_exact", "band", "override_applied", "confidence"):
                        self.assertEqual(actual[key], want[key])
                    for key in "TVRC":
                        # Sponsor's binary floating-point display rounding varies by 0.01.
                        self.assertAlmostEqual(actual["pillars"][key], want["pillars"][key], delta=.010001)
                    self.assertEqual(actual["confidence_inputs"]["current"], want["confidence_inputs"]["current"])
                    validate(actual, self.adapter.schemas["score"])

    def test_individual_and_combined_levers(self):
        r = score_record(self.adapter, self.facility, AFTER)
        actual = {l["measure"]: l["score_after"] for l in r["levers"]}
        for want in self.expected["levers_with_warning_active"][:4]:
            self.assertEqual(actual[want["measure"]], want["score_after"])
        changed = copy.deepcopy(self.facility)
        for m in self.adapter.measures[:3]:
            changed = apply_changes(changed, m["facility_changes"])
        p = pillars(changed, self.adapter.exposure_index["AST-0001"], warning_state(self.adapter.warnings, AFTER), 1_000_000)
        self.assertAlmostEqual(p["V"], 4.55)
        self.assertAlmostEqual(p["R"], 2.5)
        self.assertEqual(round(score_value(p),1), 50.2)
        self.assertEqual(round(self.value(changed,warning_state(self.adapter.warnings, BEFORE)),1), 36.7)
        self.assertEqual(band_for(round(self.value(changed,warning_state(self.adapter.warnings, BEFORE))),p,1)[0], "Guarded")

    def test_override_and_boundaries(self):
        self.assertEqual(band_for(55,dict(T=2,V=9.2,R=7,C=8),2), ("High",True))
        self.assertEqual(band_for(55,dict(T=2,V=9.2,R=7,C=8),3), ("Elevated",False))
        for score, band in [(0,"Low"),(19,"Low"),(20,"Guarded"),(39,"Guarded"),(40,"Elevated"),(59,"Elevated"),(60,"High"),(79,"High"),(80,"Severe"),(100,"Severe")]:
            self.assertEqual(band_for(score,dict(T=0,V=0,R=0,C=0),5)[0],band)

    def test_unknown_vulnerability_and_recovery_never_safer(self):
        for original in self.adapter.facilities:
            exposures = self.adapter.exposure_index[original["asset_id"]]
            baseline = self.value(original, exposures=exposures)
            variants = []
            for field in original["continuity"]:
                f=copy.deepcopy(original); f["continuity"][field]=None; variants.append(f)
            for group, field in (("audit_domains","score"),("controls","state")):
                for i in range(len(original[group])):
                    f=copy.deepcopy(original); f[group][i][field]=None; variants.append(f)
            f=copy.deepcopy(original);f["irreplaceability"]=None;variants.append(f)
            for f in variants:
                self.assertGreaterEqual(self.value(f, exposures=exposures)+1e-10, baseline)

    def test_danger_monotonicity(self):
        warnings = warning_state(self.adapter.warnings, AFTER)
        baseline = self.value(warnings=warnings)
        for key, warning in warnings.items():
            changed=copy.deepcopy(warnings);changed[key]["likelihood"]=1
            self.assertGreaterEqual(self.value(warnings=changed)+1e-10,baseline)
            values=[]
            for level in sorted(WARNING,key=WARNING.get):
                changed=copy.deepcopy(warnings);changed[key]["warning_level"]=level
                values.append(self.value(warnings=changed))
            self.assertEqual(values, sorted(values))
        exposures=copy.deepcopy(self.adapter.exposure_index["AST-0001"])
        for exposure in exposures:
            exposure["exposed"]=True
            value=self.value(exposures=exposures)
            self.assertGreaterEqual(value+1e-10,baseline)
            baseline=value

    def test_freshness_never_changes_score(self):
        changed=copy.deepcopy(self.facility)
        for p in changed["provenance"].values():p["last_verified"]=None
        for a in changed["audit_domains"]:a["assessed_at"]=None
        for c in changed["controls"]:c["verified_at"]=None
        a=score_record(self.adapter,self.facility,AFTER)
        b=score_record(self.adapter,changed,AFTER)
        self.assertEqual(a["score_exact"],b["score_exact"])
        self.assertNotEqual(a["confidence"],b["confidence"])

    def test_missing_threat_coverage_changes_confidence_only(self):
        log=copy.deepcopy(self.adapter.warnings)
        for w in log:w["coverage"]="blind"
        a=score_record(self.adapter,self.facility,AFTER)
        b=score_record(self.adapter,self.facility,AFTER,warning_log=log)
        self.assertEqual(a["score_exact"],b["score_exact"])
        self.assertGreater(a["confidence_inputs"]["current"],b["confidence_inputs"]["current"])

    def test_warning_versions_closure_and_channel_maximum(self):
        current=warning_state(self.adapter.warnings,AFTER)
        self.assertNotIn("RSK-FLD-004",current)
        self.assertEqual(warning_state(list(reversed(self.adapter.warnings)),AFTER),current)
        duplicate=copy.deepcopy(current);duplicate['duplicate']=copy.deepcopy(current['RSK-BLOOM-001'])
        self.assertEqual(self.value(warnings=current),self.value(warnings=duplicate))

    def test_checkup_exact_transitions(self):
        self.assertTrue(checkup("High","Elevated",0))
        self.assertTrue(checkup("Severe","High",0))
        self.assertFalse(checkup("High","High",14))
        self.assertFalse(checkup("High","Severe",0))
        self.assertFalse(checkup("Low",None,None))
        self.assertTrue(checkup("Guarded","Low",15))
        self.assertTrue(checkup("High","High",15))

    def test_trend_uses_nearest_at_or_before(self):
        history=[{"computed_at":"2026-08-20T06:40:00+04:00","score":45,"band":"Elevated"},
                 {"computed_at":"2026-08-20T06:41:00+04:00","score":60,"band":"High"}]
        r=score_record(self.adapter,self.facility,AFTER,history)
        self.assertEqual(r["trend"]["d7"],26)
        self.assertIsNone(r["trend"]["d90"])

    def test_determinism_and_hash(self):
        a=score_record(self.adapter,self.facility,AFTER)
        b=score_record(self.adapter,copy.deepcopy(self.facility),AFTER)
        self.assertEqual(a,b)
        changed=copy.deepcopy(self.facility);changed['continuity']['spares_on_site']=True
        self.assertNotEqual(a['inputs_hash'],score_record(self.adapter,changed,AFTER)['inputs_hash'])

    def test_second_sample_and_sensitivity(self):
        second=Adapter(ROOT/'data_second_sample')
        self.assertEqual(len(second.facilities),12)
        self.assertTrue(second.city['population_assumed'])
        for f in second.facilities:validate(score_record(second,f,AFTER),second.schemas['score'])
        result=sensitivity(self.adapter,AFTER)
        self.assertEqual(len(result),6)
        for row in result:self.assertAlmostEqual(sum(row['weights']),1,places=3)

    def test_engine_has_no_network_dependency(self):
        with patch('socket.socket',side_effect=AssertionError('Network attempted')):
            validate(score_record(self.adapter,self.facility,AFTER),self.adapter.schemas['score'])


if __name__ == '__main__':unittest.main()
