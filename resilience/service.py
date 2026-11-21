"""Application state, append-only history and atomic warning updates."""
import hashlib
import copy
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from .adapter import canonical, parse_json, timestamp, validate
from .engine import (apply_changes, band_for, pillars, score_record, score_value,
                     sensitivity, warning_state)

BEFORE = "2026-08-26T20:00:00+04:00"
AFTER = "2026-08-27T06:40:00+04:00"


class Service:
    def __init__(self, adapter, database=":memory:", at=AFTER, replay=True):
        self.adapter, self.at = adapter, at
        self.source_adapter = adapter
        adapter.freeze_baseline()
        self.lock = threading.RLock()
        if database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(database, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS scores (id INTEGER PRIMARY KEY, asset TEXT, at TEXT, body TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS warnings (id INTEGER PRIMARY KEY, body TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, body TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS input_updates (id INTEGER PRIMARY KEY, body TEXT)")
        self.db.execute("CREATE INDEX IF NOT EXISTS asset_scores ON scores(asset)")
        signature = hashlib.sha256(canonical({key: getattr(adapter, key) for key in adapter.FILES} | {"city": adapter.city}).encode()).hexdigest()
        previous = self.db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()
        if previous and previous[0] != signature:
            self.db.close()
            raise ValueError("This history belongs to another dataset. Choose a new --db file.")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('dataset', ?)", (signature,))
        self.history = {f["asset_id"]: [] for f in adapter.facilities}
        for (body,) in self.db.execute("SELECT body FROM scores ORDER BY id"):
            row = parse_json(body)
            self.history[row["asset_id"]].append(row)
        persisted = [parse_json(r[0]) for r in self.db.execute("SELECT body FROM warnings ORDER BY id")]
        adapter.validate_warnings(adapter.warnings + persisted)
        adapter.warnings += persisted
        self.input_updates = [parse_json(r[0]) for r in self.db.execute("SELECT body FROM input_updates ORDER BY id")]
        for update in self.input_updates:
            adapter.validate_input_update(update)
        self.events = [parse_json(r[0]) for r in self.db.execute("SELECT body FROM events ORDER BY id")]
        if not any(self.history.values()):
            self.append([r for r in adapter.pilot if r["asset_id"] in self.history])
            if replay:
                self.replay_history(at)
        self.records = {}
        self.rescore(at)

    def append(self, records):
        with self.db:
            for record in records:
                validate(record, self.adapter.schemas["score"])
                self.db.execute("INSERT INTO scores(asset,at,body) VALUES(?,?,?)",
                                (record["asset_id"], record["computed_at"], canonical(record)))
        for record in records:
            self.history[record["asset_id"]].append(record)

    def replay_history(self, through):
        end = timestamp(through)
        start_date = self.adapter.city.get("warning_log", {}).get("day_1")
        if not start_date:
            start_date = min((timestamp(w["updated_at"]).date().isoformat() for w in self.adapter.warnings), default=end.date().isoformat())
        start = datetime.fromisoformat(start_date).replace(tzinfo=end.tzinfo)
        # Safety bound for arbitrary datasets; explicit history still loads in full.
        start = max(start, end - timedelta(days=100))
        moments = set()
        while start < end:
            moments.add(start.isoformat())
            start += timedelta(days=1)
        moments.update(w["updated_at"] for w in self.adapter.warnings if timestamp(w["updated_at"]) < end and timestamp(w["updated_at"]) >= end - timedelta(days=100))
        for at in sorted(moments, key=timestamp):
            view = self.source_adapter.at_time(at, self.input_updates)
            rows = [score_record(view, f, at, self.history[f["asset_id"]]) for f in view.facilities]
            self.append(rows)

    def rescore(self, at, asset_ids=None, log=None):
        timestamp(at)
        with self.lock:
            view = self.source_adapter.at_time(at, self.input_updates)
            ids = set(view.by_id if asset_ids is None else asset_ids)
            rows = [score_record(view, view.by_id[a], at, self.history[a], warning_log=log) for a in sorted(ids)]
            self.append(rows)
            self.adapter = view
            self.records.update({r["asset_id"]: r for r in rows})
            self.at = at
            return rows

    def daily_tick(self, at):
        """One full run on the next local calendar day; injectable clock for tests."""
        with self.lock:
            if timestamp(at).date() > timestamp(self.at).date():
                return self.rescore(at)
            return []

    def add_event(self, event):
        with self.db:
            self.db.execute("INSERT INTO events(body) VALUES(?)", (canonical(event),))
        self.events.append(event)

    def ingest(self, rows):
        if isinstance(rows, dict):
            rows = [rows]
        self.adapter.validate_warnings(rows)
        if not rows:
            raise ValueError("Warning file is empty")
        with self.lock:
            start = time.perf_counter()
            existing = {canonical(w) for w in self.adapter.warnings}
            new = [r for r in rows if canonical(r) not in existing]
            proposed = self.adapter.warnings + new
            self.adapter.validate_warnings(proposed)
            old = warning_state(self.adapter.warnings, self.at, include_closed=True)
            at = max([self.at] + [w["updated_at"] for w in rows], key=timestamp)
            view = self.source_adapter.at_time(at, self.input_updates)
            after = warning_state(proposed, at, include_closed=True)
            channels = set()
            for key in set(old) | set(after):
                if old.get(key) != after.get(key):
                    channels.update((old.get(key) or {}).get("channels", []))
                    channels.update((after.get(key) or {}).get("channels", []))
            ids = sorted(a for a, exps in view.exposure_index.items()
                         if any(e["exposed"] and e["channel_id"] in channels for e in exps + self.adapter.exposure_index[a])
                         or view.by_id[a] != self.adapter.by_id[a] or exps != self.adapter.exposure_index[a]
                         or view.city["population"] != self.adapter.city["population"])
            records = [score_record(view, view.by_id[a], at, self.history[a], warning_log=proposed) for a in ids]
            for row in records:
                validate(row, self.adapter.schemas["score"])
            event = {"at": at, "kind": "warning_import", "versions": len(new), "affected": ids,
                     "elapsed_ms": round((time.perf_counter() - start) * 1000, 1)}
            # Commit warning versions, resulting scores and their event together.
            with self.db:
                self.db.executemany("INSERT INTO warnings(body) VALUES(?)", [(canonical(w),) for w in new])
                self.db.executemany("INSERT INTO scores(asset,at,body) VALUES(?,?,?)",
                                    [(r["asset_id"], r["computed_at"], canonical(r)) for r in records])
                self.db.execute("INSERT INTO events(body) VALUES(?)", (canonical(event),))
            self.source_adapter.warnings = proposed
            view.warnings = proposed
            self.adapter = view
            self.at = at
            for r in records:
                self.history[r["asset_id"]].append(r)
                self.records[r["asset_id"]] = r
            self.events.append(event)
            return event

    def ingest_inputs(self, update):
        """Validate and persist a dated source update, with a full atomic run."""
        self.source_adapter.validate_input_update(update)
        update = copy.deepcopy(update)
        with self.lock:
            if any(canonical(u) == canonical(update) for u in self.input_updates):
                return {"at": self.at, "kind": "input_import", "versions": 0, "affected": [], "elapsed_ms": 0}
            if timestamp(update["effective_at"]) < timestamp(self.at):
                raise ValueError("Input updates cannot predate the active snapshot. Replay earlier data separately.")
            if any(timestamp(u["effective_at"]) >= timestamp(update["effective_at"]) for u in self.input_updates):
                raise ValueError("Use an effective_at later than the last recorded input update")
            start = time.perf_counter()
            proposed = self.input_updates + [update]
            at = update["effective_at"]
            view = self.source_adapter.at_time(at, proposed)
            records = [score_record(view, f, at, self.history[f["asset_id"]]) for f in view.facilities]
            for record in records:
                validate(record, view.schemas["score"])
            event = {"at": at, "kind": "input_import", "versions": 1, "affected": sorted(view.by_id),
                     "elapsed_ms": round((time.perf_counter() - start) * 1000, 1)}
            with self.db:
                self.db.execute("INSERT INTO input_updates(body) VALUES(?)", (canonical(update),))
                self.db.executemany("INSERT INTO scores(asset,at,body) VALUES(?,?,?)",
                                    [(r["asset_id"], r["computed_at"], canonical(r)) for r in records])
                self.db.execute("INSERT INTO events(body) VALUES(?)", (canonical(event),))
            self.input_updates = proposed
            self.adapter = view
            self.at = at
            for record in records:
                self.history[record["asset_id"]].append(record)
                self.records[record["asset_id"]] = record
            self.events.append(event)
            return event

    def dashboard(self):
        with self.lock:
            return {"city": self.adapter.city, "at": self.at,
                    "facilities": [{**f, "result": self.records[f["asset_id"]]} for f in self.adapter.facilities],
                    "warnings": list(warning_state(self.adapter.warnings, self.at).values()),
                    "warning_log": [w for w in self.adapter.warnings if timestamp(w["updated_at"]) <= timestamp(self.at)],
                    "channels": self.adapter.channels,
                    "input_updates": [u for u in self.input_updates if timestamp(u["effective_at"]) <= timestamp(self.at)],
                    "events": [e for e in self.events if timestamp(e["at"]) <= timestamp(self.at)][-30:]}

    def detail(self, asset_id):
        with self.lock:
            if asset_id not in self.records:
                raise ValueError("Unknown asset")
            # Collapse repeat runs at one instant for charting; retain all rows in SQLite.
            points = {r["computed_at"]: r for r in self.history[asset_id] if timestamp(r["computed_at"]) <= timestamp(self.at)}
            return {"record": self.records[asset_id],
                    "history": [{"at": r["computed_at"], "score": r["score"]} for r in sorted(points.values(), key=lambda r: timestamp(r["computed_at"]))],
                    "plans": [p for p in self.adapter.plan_links if p["asset_id"] == asset_id]}

    def scenario(self, asset_id, measure_ids):
        if asset_id not in self.adapter.by_id or not isinstance(measure_ids, list):
            raise ValueError("Invalid scenario")
        measures = {m["measure_id"]: m for m in self.adapter.measures if m["asset_id"] == asset_id}
        if any(m not in measures for m in measure_ids):
            raise ValueError("A selected measure does not belong to this facility")
        changes, cost, opex = {}, 0, 0
        for key in sorted(set(measure_ids)):
            m = measures[key]
            for path, value in m["facility_changes"].items():
                if path in changes and changes[path] != value:
                    raise ValueError("Selected measures contain conflicting changes")
                changes[path] = value
            cost += m["capex_aed"]
            opex += m["opex_aed_per_year"]
        facility = apply_changes(self.adapter.by_id[asset_id], changes)
        validate(facility, self.adapter.schemas["facility"])
        p = pillars(facility, self.adapter.exposure_index[asset_id], warning_state(self.adapter.warnings, self.at), self.adapter.city["population"])
        exact = score_value(p)
        band, override = band_for(int(exact + .5), p, facility["category"])
        return {"score_after": round(exact, 1), "band": band, "override_applied": override,
                "pillars": {k: round(v, 2) for k, v in p.items()}, "capex_aed": cost, "opex_aed_per_year": opex}

    def weight_sensitivity(self):
        return sensitivity(self.adapter, self.at)
