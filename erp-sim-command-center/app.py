#!/usr/bin/env python3
"""Local web server for ERPsim Decision Command Center."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import json, os, re, time

from src.engine import state_json, load_data, build_plan

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "data" / "uploads"
SNAPSHOTS = ROOT / "data" / "snapshots"
UPLOADS.mkdir(parents=True, exist_ok=True)
SNAPSHOTS.mkdir(parents=True, exist_ok=True)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "static"), **kwargs)

    def log_message(self, fmt, *args):
        print("[ERPsim] " + fmt % args)

    def _json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/state":
            qs = parse_qs(url.query); target = qs.get("round", [None])[0]
            mode = qs.get("mode", ["auto"])[0]; freq = qs.get("frequency", [None])[0]
            try: self._json(state_json(UPLOADS, target, mode, int(freq) if freq else None))
            except Exception as e: self._json({"error": str(e)}, 500)
            return
        if url.path == "/api/health": self._json({"ok": True}); return
        if url.path == "/": self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        if url.path == "/api/upload":
            # Multipart parser is in the Python standard library.
            import email.parser, email.policy
            mime = f"Content-Type: {self.headers.get('Content-Type')}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
            msg = email.parser.BytesParser(policy=email.policy.default).parsebytes(mime)
            saved = []
            for part in msg.iter_attachments():
                name = Path(part.get_filename() or "report.xlsx").name
                if not name.lower().endswith(".xlsx"): continue
                safe = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
                (UPLOADS / safe).write_bytes(part.get_payload(decode=True) or b"")
                saved.append(safe)
            if not saved: self._json({"error": "Choose an Excel .xlsx report."}, 400); return
            self._json({"saved": saved}); return
        if url.path == "/api/snapshot":
            try:
                payload = json.loads(body.decode("utf-8"))
                target = int(payload.get("round", 1))
                data = load_data(UPLOADS); plan = build_plan(data, target)
                stamp = time.strftime("%Y%m%d-%H%M%S")
                path = SNAPSHOTS / f"round_{target:02d}_{stamp}.json"
                path.write_text(json.dumps({"round": target, "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"), "plan": plan}, indent=2), encoding="utf-8")
                self._json({"saved": path.name})
            except Exception as e: self._json({"error": str(e)}, 500)
            return
        self._json({"error": "Not found"}, 404)

def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("ERPsim Decision Command Center: http://127.0.0.1:8765")
    print("Press Ctrl+C to stop.")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nStopping ERPsim Command Center.")
    finally: server.server_close()

if __name__ == "__main__": main()
