#!/usr/bin/env python3
"""Serve movie-alpha/; reuse an existing Conflux movie server if already up."""

from __future__ import annotations

import http.server
import socketserver
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "movie-alpha"
PORTS = range(8877, 8890)


def already_serving(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.4) as r:
            body = r.read(240).decode("utf-8", "ignore")
            return r.status == 200 and "Conflux Atlas" in body
    except Exception:
        return False


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)


def main() -> int:
    if not (ROOT / "index.html").exists():
        print(f"missing {ROOT / 'index.html'}", file=sys.stderr)
        return 1

    for port in PORTS:
        if already_serving(port):
            print(f"Already running — open http://127.0.0.1:{port}/")
            return 0

    socketserver.TCPServer.allow_reuse_address = True
    for port in PORTS:
        try:
            with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
                print(f"Open http://127.0.0.1:{port}/  (Ctrl+C to stop)")
                httpd.serve_forever()
        except OSError as e:
            if getattr(e, "errno", None) == 98:
                continue
            raise
    print("No free port in 8877–8889", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
