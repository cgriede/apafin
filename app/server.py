"""One-page server. Keys stay here."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.config import config_from_body, default_config
from app.search import run_search

STATIC = Path(__file__).resolve().parent / "static" / "index.html"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/config":
            self._json(default_config().to_json())
            return
        if self.path.split("?", 1)[0] in ("/", "/index.html"):
            body = STATIC.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/search":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode() or "{}")
            cfg = config_from_body(body)
            mode = "sample" if body.get("mode") == "sample" else "live"
            self._json(run_search(cfg, mode=mode))
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, status=400)

    def _json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    port = int(os.environ.get("APAFIN_PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"apafin listening on {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
