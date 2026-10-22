#!/usr/bin/env python3
"""Connectivity tester. One image, three roles chosen by the ROLE env var.

- frontend: serves a small web UI and a /check endpoint that probes DNS, TCP,
  and HTTP reachability from inside the pod.
- backend:  answers GET on any path with 200, so a 403 seen by a client is the
  network policy talking, not the app.
- database: a stand-in target that just holds its port open.

No third-party dependencies. Standard library only.
"""
import json
import os
import socket
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROLE = os.environ.get("ROLE", "frontend")
PORT = int(os.environ.get("PORT", "8080"))
HERE = os.path.dirname(os.path.abspath(__file__))


def probe(kind, target, port, path):
    """Return (ok, detail) for one reachability test. Never raises."""
    try:
        if kind == "dns":
            socket.getaddrinfo(target, None)
            return True, f"resolved {target}"
        if kind == "tcp":
            with socket.create_connection((target, int(port)), timeout=3):
                return True, f"tcp {target}:{port} open"
        if kind == "http":
            url = f"http://{target}:{port}{path}"
            with urllib.request.urlopen(url, timeout=3) as r:  # noqa: S310 (internal demo)
                return True, f"http {r.status} {url}"
        if kind == "https":
            url = f"https://{target}{path}"
            with urllib.request.urlopen(url, timeout=4) as r:  # noqa: S310
                return True, f"https {r.status} {target}"
    except urllib.error.HTTPError as e:
        return False, f"http {e.code}"
    except Exception as e:  # noqa: BLE001 (surface any failure to the UI)
        return False, f"{type(e).__name__}: {e}"
    return False, "unknown probe type"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if ROLE == "frontend" and u.path == "/":
            with open(os.path.join(HERE, "static", "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html")
        if ROLE == "frontend" and u.path == "/check":
            q = parse_qs(u.query)
            ok, detail = probe(
                q.get("type", ["tcp"])[0],
                q.get("target", [""])[0],
                q.get("port", ["80"])[0],
                q.get("path", ["/"])[0],
            )
            return self._send(200, json.dumps({"ok": ok, "detail": detail}), "application/json")
        # backend and database answer every GET, so a block is clearly the policy.
        if ROLE in ("backend", "database"):
            return self._send(200, f"{ROLE} {u.path}")
        return self._send(404, "not found")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"{ROLE} listening on :{PORT}", flush=True)
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
