"""Single input boundary; validates the supplied schema vocabulary offline."""
import json
import copy
import math
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("A timestamp must include its UTC offset")
    return result


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def parse_json(text):
    def invalid(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    return json.loads(text, parse_constant=invalid)


def validate(value, schema, path="$ "):
    """Implements every validation keyword in the unmodified sponsor schemas.

    This deliberately small validator is not a general Draft 2020-12 engine.
    Unknown validation keywords fail closed; annotations do not affect validation.
    """
    supported = {"$schema", "$id", "title", "description", "type", "enum", "properties",
                 "required", "additionalProperties", "items", "minimum", "maximum", "pattern"}
    if set(schema) - supported:
        raise ValueError(f"Unsupported schema keywords: {set(schema) - supported}")
    types = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "boolean": isinstance(value, bool),
             "null": value is None,
             "number": type(value) in (int, float),
             "integer": type(value) is int or (type(value) is float and value.is_integer())}
    wanted = schema.get("type", list(types))
    if isinstance(wanted, str):
        wanted = [wanted]
    if not any(types.get(t, False) for t in wanted):
        raise ValueError(f"{path}: expected {' / '.join(wanted)}")
    if "enum" in schema and not any(canonical(value) == canonical(x) for x in schema["enum"]):
        raise ValueError(f"{path}: invalid value {value!r}")
    if type(value) in (int, float):
        if not math.isfinite(value):
            raise ValueError(f"{path}: number must be finite")
        if value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            raise ValueError(f"{path}: number out of range")
    if isinstance(value, str) and "pattern" in schema:
        if not re.search(schema["pattern"], value):
            raise ValueError(f"{path}: invalid format")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f"{path}.{key}: required field missing")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in props:
                validate(item, props[key], f"{path}.{key}")
            elif isinstance(extra, dict):
                validate(item, extra, f"{path}.{key}")
            elif extra is False:
                raise ValueError(f"{path}.{key}: unexpected field")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]")


class Adapter:
    FILES = {"facilities": "facility", "channels": "channel", "exposures": "exposure",
             "warnings": "warning", "measures": "measure", "plan_links": "plan_link"}

    def __init__(self, directory, population=None):
        self.directory = Path(directory)
        self.schemas = {name: parse_json((ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
                        for name in [*self.FILES.values(), "score", "sub_asset"]}
        for filename, schema in self.FILES.items():
            rows = parse_json((self.directory / f"{filename}.json").read_text(encoding="utf-8"))
            self.validate_rows(rows, schema)
            setattr(self, filename, rows)
        city = self.directory / "city.json"
        self.city = parse_json(city.read_text(encoding="utf-8")) if city.exists() else {"city_en": "Second sample city", "timezone": "+04:00"}
        self.city["population"] = population if population is not None else self.city.get("population", 1_000_000)
        self.city["population_assumed"] = not city.exists() and population is None
        if type(self.city["population"]) is not int or self.city["population"] <= 0:
            raise ValueError("City population must be a positive integer")
        self.by_id = self.unique(self.facilities, "asset_id")
        self.unique(self.channels, "channel_id")
        self.unique(self.measures, "measure_id")
        pairs = [(e["asset_id"], e["channel_id"]) for e in self.exposures]
        if len(set(pairs)) != len(pairs):
            raise ValueError("Duplicate facility/channel exposure")
        channel_ids = {c["channel_id"] for c in self.channels}
        for row in self.exposures + self.measures + self.plan_links:
            if row["asset_id"] not in self.by_id:
                raise ValueError(f"Unknown asset: {row['asset_id']}")
        for row in self.exposures:
            if row["channel_id"] not in channel_ids:
                raise ValueError("Exposure references an unknown channel")
        self.validate_warnings(self.warnings)
        self.exposure_index = {key: [] for key in self.by_id}
        for row in self.exposures:
            self.exposure_index[row["asset_id"]].append(row)
        pilot = self.directory / "score_history_pilot.json"
        self.pilot = parse_json(pilot.read_text(encoding="utf-8")) if pilot.exists() else []
        self.validate_rows(self.pilot, "score")
        subfile = self.directory / "sub_assets.json"
        self.sub_assets = parse_json(subfile.read_text(encoding="utf-8")) if subfile.exists() else []
        self.validate_rows(self.sub_assets, "sub_asset")
        sub_ids = self.unique(self.sub_assets, "sub_asset_id")
        for part in self.sub_assets:
            if part["asset_id"] not in self.by_id or any(s not in sub_ids for s in part["upstream"]):
                raise ValueError("Sub-asset references an unknown facility or upstream part")
        self.input_updates = []
        self.freeze_baseline()

    def freeze_baseline(self):
        """Keep the supplied static baseline separate from dated operator updates."""
        self.baseline = copy.deepcopy({"facilities": self.facilities, "exposures": self.exposures,
                                       "population": self.city["population"]})

    def validate_input_update(self, update):
        if not isinstance(update, dict) or set(update) - {"effective_at", "facilities", "exposures", "population"}:
            raise ValueError("Input update requires effective_at and facilities, exposures or population")
        if not isinstance(update.get("effective_at"), str):
            raise ValueError("Input update needs an effective_at timestamp with UTC offset")
        timestamp(update["effective_at"])
        if not update.get("facilities") and not update.get("exposures") and "population" not in update:
            raise ValueError("Input update is empty")
        for key, schema in (("facilities", "facility"), ("exposures", "exposure")):
            self.validate_rows(update.get(key, []), schema)
        self.unique(update.get("facilities", []), "asset_id")
        exposures = update.get("exposures", [])
        if len({(e["asset_id"], e["channel_id"]) for e in exposures}) != len(exposures):
            raise ValueError("Duplicate facility/channel in input update")
        channels = {c["channel_id"] for c in self.channels}
        for row in update.get("facilities", []) + exposures:
            if row["asset_id"] not in self.by_id:
                raise ValueError("Input update references an unknown asset")
        for row in exposures:
            if row["channel_id"] not in channels:
                raise ValueError("Input update references an unknown channel")
        for row in update.get("facilities", []):
            if any(d["upstream_asset_id"] not in self.by_id for d in row["dependencies"]):
                raise ValueError("Facility update references an unknown dependency")
            self.unique(row["audit_domains"], "domain")
            self.unique(row["controls"], "name")
        if "population" in update and (type(update["population"]) is not int or update["population"] <= 0):
            raise ValueError("Updated population must be a positive integer")

    def at_time(self, at, updates=None):
        """Return a view of source inputs at a time; never edit the baseline files."""
        updates = self.input_updates if updates is None else updates
        active = [u for u in updates if timestamp(u["effective_at"]) <= timestamp(at)]
        view = copy.copy(self)
        view.input_updates = updates
        if active:
            values = copy.deepcopy(self.baseline)
            facilities = {f["asset_id"]: f for f in values["facilities"]}
            exposures = {(e["asset_id"], e["channel_id"]): e for e in values["exposures"]}
            for update in sorted(active, key=lambda u: timestamp(u["effective_at"])):
                facilities.update({f["asset_id"]: copy.deepcopy(f) for f in update.get("facilities", [])})
                exposures.update({(e["asset_id"], e["channel_id"]): copy.deepcopy(e) for e in update.get("exposures", [])})
                values["population"] = update.get("population", values["population"])
            view.facilities = list(facilities.values()); view.exposures = list(exposures.values())
            view.city = {**self.city, "population": values["population"]}
            if any("population" in u for u in active):
                view.city["population_assumed"] = False
        else:
            view.facilities = self.baseline["facilities"]
            view.exposures = self.baseline["exposures"]
            view.city = {**self.city, "population": self.baseline["population"]}
        view.by_id = {f["asset_id"]: f for f in view.facilities}
        view.exposure_index = {a: [] for a in view.by_id}
        for row in view.exposures:
            view.exposure_index[row["asset_id"]].append(row)
        return view

    def inputs_for(self, asset_id, at):
        """Per-asset historical facts, avoiding a full-city copy for each score."""
        facility = next(f for f in self.baseline["facilities"] if f["asset_id"] == asset_id)
        exposures = {e["channel_id"]: e for e in self.baseline["exposures"] if e["asset_id"] == asset_id}
        population = self.baseline["population"]
        for update in sorted(self.input_updates, key=lambda u: timestamp(u["effective_at"])):
            if timestamp(update["effective_at"]) > timestamp(at):
                break
            facility = next((f for f in update.get("facilities", []) if f["asset_id"] == asset_id), facility)
            exposures.update({e["channel_id"]: e for e in update.get("exposures", []) if e["asset_id"] == asset_id})
            population = update.get("population", population)
        return {"facility": facility, "exposures": list(exposures.values()), "population": population}

    @staticmethod
    def unique(rows, field):
        result = {row[field]: row for row in rows}
        if len(result) != len(rows):
            raise ValueError(f"Duplicate {field}")
        return result

    def validate_rows(self, rows, schema):
        if not isinstance(rows, list):
            raise ValueError(f"{schema}: expected a JSON array")
        for i, row in enumerate(rows):
            validate(row, self.schemas[schema], f"{schema}[{i}]")

    def validate_warnings(self, rows):
        self.validate_rows(rows, "warning")
        ids = {c["channel_id"] for c in self.channels}
        seen = {}
        for row in rows:
            at = timestamp(row["updated_at"])
            if not row["channels"] or not set(row["channels"]) <= ids:
                raise ValueError("Warning must reference known channels")
            if not row["likelihood_low"] <= row["likelihood"] <= row["likelihood_high"]:
                raise ValueError("Warning likelihood must fall within its bounds")
            key = (row["risk_id"], at)
            if key in seen and canonical(seen[key]) != canonical(row):
                raise ValueError("Conflicting warning versions at the same timestamp")
            seen[key] = row
