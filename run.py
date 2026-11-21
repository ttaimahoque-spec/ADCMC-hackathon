#!/usr/bin/env python3
"""Run the local dashboard: python3 run.py (Python 3.10+, no pip install)."""
import argparse
import json
import mimetypes
import threading
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from resilience.adapter import Adapter, ROOT, parse_json, timestamp
from resilience.service import Service, BEFORE, AFTER
from resilience.reporting import capture_report, render_report, report_csp


def create_service(data, population=None, database=None, at=AFTER, demo_before=False, replay=True):
    """Fresh warning-ingestion rehearsal, or the normal persistent application."""
    adapter = Adapter(data, population)
    if demo_before:
        if database is not None:
            raise ValueError("--demo-before uses a fresh in-memory history; omit --db.")
        # Withhold future versions so loading the supplied red warning is a new import.
        # Original starter-pack files and the normal saved history are never changed.
        adapter.warnings = [w for w in adapter.warnings if timestamp(w["updated_at"]) <= timestamp(BEFORE)]
        return Service(adapter, ":memory:", BEFORE, replay=replay)
    return Service(adapter, database or str(ROOT / "var" / "history.sqlite3"), at, replay=replay)


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, value, status=200, mime="application/json", csp=None):
            body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode() if mime == "application/json" else value
            self.send_response(status)
            self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") else ""))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", csp or "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            try:
                if path == "/report":
                    query = parse_qs(urlparse(self.path).query)
                    snapshot = capture_report(service, query.get("asset", [None])[0],
                                              query.get("measure", []), query.get("scope", ["portfolio"])[0])
                    return self.respond(render_report(snapshot).encode("utf-8"), mime="text/html", csp=report_csp())
                with service.lock:
                    if path == "/api/state":
                        return self.respond(service.dashboard())
                    if path == "/api/detail":
                        asset = parse_qs(urlparse(self.path).query).get("asset", [""])[0]
                        return self.respond(service.detail(asset))
                    if path == "/api/input-template":
                        asset = parse_qs(urlparse(self.path).query).get("asset", [""])[0]
                        if asset not in service.adapter.by_id:
                            raise ValueError("Unknown asset")
                        return self.respond({"effective_at": service.at,
                                             "facilities": [service.adapter.by_id[asset]],
                                             "exposures": service.adapter.exposure_index[asset]})
                    if path == "/api/export":
                        return self.respond(list(service.records.values()))
                    if path == "/api/sensitivity":
                        return self.respond(service.weight_sensitivity())
                files = {"/": "home.html", "/index.html": "home.html", "/dashboard": "index.html", "/dashboard/": "index.html", "/home.css": "home.css", "/home.js": "home.js", "/styles.css": "styles.css", "/asset-viewer.css": "asset-viewer.css", "/app.js": "app.js", "/map3d.js": "map3d.js", "/asset3d.js": "asset3d.js", "/asset-renderer.js": "asset-renderer.js", "/visuals.js": "visuals.js", "/favicon.svg": "favicon.svg"}
                if path not in files:
                    return self.respond({"error": "Not found"}, 404)
                file = ROOT / "web" / files[path]
                self.respond(file.read_bytes(), mime=mimetypes.guess_type(file)[0] or "text/plain")
            except (ValueError, KeyError) as error:
                self.respond({"error": str(error)}, 400)

        def do_POST(self):
            # Same-origin JSON API for this local, single-analyst application.
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                return self.respond({"error": "Cross-origin writes are disabled"}, 403)
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.respond({"error": "Expected application/json"}, 415)
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= 2_000_000:
                    raise ValueError("Provide a JSON file smaller than 2 MB")
                data = parse_json(self.rfile.read(length))
                path = urlparse(self.path).path
                with service.lock:
                    if path == "/api/warnings":
                        return self.respond(service.ingest(data))
                    if path == "/api/inputs":
                        return self.respond(service.ingest_inputs(data))
                    if path == "/api/scenario":
                        return self.respond(service.scenario(data["asset_id"], data["measure_ids"]))
                    if path == "/api/replay":
                        if data.get("phase") not in ("before", "after"):
                            raise ValueError("Unknown replay phase")
                        service.rescore(BEFORE if data["phase"] == "before" else AFTER)
                        return self.respond({"at": service.at})
                return self.respond({"error": "Not found"}, 404)
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                self.respond({"error": str(error)}, 400)

        def log_message(self, format, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--db", type=str, help="History database; default: var/history.sqlite3")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--population", type=int)
    parser.add_argument("--at", default=AFTER)
    parser.add_argument("--live", action="store_true", help="Use wall time and rescore all facilities each day")
    parser.add_argument("--demo-before", action="store_true", help="Fresh in-memory baseline; load examples/warning_red.json to demonstrate a new warning")
    args = parser.parse_args()
    if args.demo_before and (args.live or args.db is not None or args.at != AFTER):
        parser.error("--demo-before fixes the baseline date and uses temporary history; omit --live, --db and --at.")
    now = lambda: datetime.now(timezone(timedelta(hours=4))).replace(microsecond=0).isoformat()
    print("Loading synthetic city and score history…", flush=True)
    service = create_service(args.data, args.population, args.db, now() if args.live else args.at, args.demo_before)
    if args.demo_before:
        print("Fresh demo baseline: load examples/warning_red.json. Rehearsal history is discarded when this process stops.", flush=True)
    stop = threading.Event()
    def daily():
        while not stop.wait(30):
            service.daily_tick(now())
    if args.live:
        threading.Thread(target=daily, daemon=True).start()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(service))
    print(f"Asset resilience dashboard: http://{args.host}:{server.server_port}\nPress Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        service.db.close()


if __name__ == "__main__":
    main()
