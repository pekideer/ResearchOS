#!/usr/bin/env python3
"""Serve a portable ResearchOS HTML table with local open helpers."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ZOTERO_URI_RE = re.compile(r"^zotero://(?:select|open-pdf)/library/items/[A-Z0-9]{8}$")


def open_default(target: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(target)  # type: ignore[attr-defined]
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def inject_base(html: str, html_path: Path) -> str:
    base_uri = html_path.parent.resolve().as_uri() + "/"
    base_tag = f'<base href="{base_uri}">'
    if "<base " in html.lower():
        return html
    return re.sub(r"(<head[^>]*>)", r"\1\n" + base_tag, html, count=1, flags=re.I)


def make_handler(html_path: Path):
    base_dir = html_path.parent.resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *args: object) -> None:
            return

        def respond_text(self, status: int, text: str) -> None:
            data = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path not in {"/", "/index.html"}:
                self.respond_text(404, "not found")
                return
            html = html_path.read_text(encoding="utf-8-sig")
            data = inject_base(html, html_path).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            try:
                if parsed.path == "/__researchos_open/zotero":
                    uri = query.get("uri", [""])[0]
                    if not ZOTERO_URI_RE.match(uri):
                        self.respond_text(400, "invalid zotero uri")
                        return
                    open_default(uri)
                    self.respond_text(200, "ok")
                    return
                if parsed.path == "/__researchos_open/card":
                    raw_path = query.get("path", [""])[0]
                    if not raw_path or re.match(r"^[A-Za-z]:[\\/]", raw_path) or raw_path.startswith("file:"):
                        self.respond_text(400, "invalid path")
                        return
                    target = (base_dir / urllib.parse.unquote(raw_path)).resolve()
                    if target.suffix.lower() != ".md" or not target.exists():
                        self.respond_text(404, "card not found")
                        return
                    open_default(str(target))
                    self.respond_text(200, "ok")
                    return
            except Exception as exc:  # pragma: no cover - runtime environment dependent.
                self.respond_text(500, str(exc))
                return
            self.respond_text(404, "not found")

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Open a portable ResearchOS HTML table with local link helpers.")
    parser.add_argument("--html", required=True, help="HTML table path.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="Start the server without opening a browser.")
    args = parser.parse_args()

    html_path = Path(args.html).resolve()
    if not html_path.exists():
        raise FileNotFoundError(html_path)

    server = ThreadingHTTPServer((args.host, args.port), make_handler(html_path))
    url = f"http://{args.host}:{args.port}/"
    print(f"Serving {html_path.name} at {url}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
