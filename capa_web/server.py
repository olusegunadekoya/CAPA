"""Built-in HTTP server for CAPA Web (Python standard library only).

Routes
------
GET  /                         -> static/index.html (single-page app)
GET  /static/*                 -> css / js assets
GET  /api/bootstrap            -> settings + vocabularies
GET  /api/metrics              -> dashboard data
GET  /api/capas                -> register (search/status/priority/order)
GET  /api/capa/<id>            -> full CAPA detail incl. report text
GET  /api/tasks                -> cross-CAPA task list
POST /api/capa                 -> create
PUT  /api/capa/<id>            -> update
DELETE /api/capa/<id>          -> delete
POST /api/capa/<id>/comment    -> add activity comment
POST /api/capa/<id>/task       -> add action-item task
PUT  /api/task/<id>            -> toggle done
DELETE /api/task/<id>          -> delete task
POST /api/capa/<id>/document   -> attach document reference
DELETE /api/document/<id>      -> remove document reference
PUT  /api/settings             -> save organisation settings
GET  /export/register.csv      -> download CAPA register
GET  /export/capa/<id>.txt     -> download single CAPA report

Run via ``python run_web.py`` or ``python -m capa_web.server``.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capa_app import database as db          # noqa: E402
from capa_web import api                     # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class CapaRequestHandler(BaseHTTPRequestHandler):
    server_version = "CAPAWeb/1.0"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ log
    def log_message(self, fmt, *args):  # quieter console
        sys.stderr.write("[capa-web] %s\n" % (fmt % args))

    # ------------------------------------------------------------- plumbing
    def _send(self, status: int, body: bytes, ctype: str,
              extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(status, json.dumps(obj).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, UnicodeDecodeError):
            raise api.ApiError("Request body must be valid JSON")

    # ------------------------------------------------------------ dispatch
    def do_GET(self):
        self._dispatch("GET")

    def do_HEAD(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path.startswith("/api/"):
                self._api(method, path, query)
            elif path.startswith("/export/"):
                self._export(method, path)
            elif path == "/" or not path.startswith("/static/"):
                self._static("index.html")
            else:
                self._static(path[len("/static/"):])
        except api.ApiError as exc:
            self._error(exc.status, str(exc))
        except BrokenPipeError:
            pass
        except Exception as exc:  # pragma: no cover - safety net
            self._error(500, f"Internal error: {exc}")

    # ----------------------------------------------------------------- api
    _API_ROUTES: list[tuple[str, re.Pattern, str]] = [
        ("GET",    re.compile(r"^/api/bootstrap$"), "bootstrap"),
        ("GET",    re.compile(r"^/api/metrics$"), "metrics"),
        ("GET",    re.compile(r"^/api/capas$"), "capa_list"),
        ("GET",    re.compile(r"^/api/capa/(?P<id>\d+)$"), "capa_get"),
        ("PUT",    re.compile(r"^/api/capa/(?P<id>\d+)$"), "capa_update"),
        ("DELETE", re.compile(r"^/api/capa/(?P<id>\d+)$"), "capa_delete"),
        ("POST",   re.compile(r"^/api/capa$"), "capa_create"),
        ("POST",   re.compile(r"^/api/capa/(?P<id>\d+)/comment$"), "comment"),
        ("POST",   re.compile(r"^/api/capa/(?P<id>\d+)/task$"), "task_add"),
        ("POST",   re.compile(r"^/api/capa/(?P<id>\d+)/document$"), "doc_add"),
        ("PUT",    re.compile(r"^/api/task/(?P<id>\d+)$"), "task_toggle"),
        ("DELETE", re.compile(r"^/api/task/(?P<id>\d+)$"), "task_delete"),
        ("DELETE", re.compile(r"^/api/document/(?P<id>\d+)$"), "doc_delete"),
        ("GET",    re.compile(r"^/api/tasks$"), "task_list"),
        ("PUT",    re.compile(r"^/api/settings$"), "settings_save"),
    ]

    def _api(self, method: str, path: str, query: dict) -> None:
        for route_method, pattern, name in self._API_ROUTES:
            m = pattern.match(path)
            if not m or route_method != method:
                continue
            cid = int(m.group("id")) if m.groupdict().get("id") else None
            if name == "bootstrap":
                self._json(api.get_bootstrap())
            elif name == "metrics":
                self._json(api.get_metrics())
            elif name == "capa_list":
                self._json(api.list_capas(query))
            elif name == "capa_get":
                self._json(api.get_capa(cid))
            elif name == "capa_create":
                self._json(api.create_capa(self._read_json()), 201)
            elif name == "capa_update":
                self._json(api.update_capa(cid, self._read_json()))
            elif name == "capa_delete":
                self._json(api.delete_capa(cid))
            elif name == "comment":
                self._json(api.add_comment(cid, self._read_json()), 201)
            elif name == "task_add":
                self._json(api.add_task(cid, self._read_json()), 201)
            elif name == "task_toggle":
                self._json(api.toggle_task(cid, self._read_json()))
            elif name == "task_delete":
                self._json(api.delete_task(cid))
            elif name == "doc_add":
                self._json(api.add_document(cid, self._read_json()), 201)
            elif name == "doc_delete":
                self._json(api.delete_document(cid))
            elif name == "task_list":
                self._json(api.list_all_tasks())
            elif name == "settings_save":
                self._json(api.save_settings(self._read_json()))
            return
        self._error(404, f"No API route for {method} {path}")

    # -------------------------------------------------------------- export
    def _export(self, method: str, path: str) -> None:
        if method != "GET":
            self._error(405, "Use GET for exports")
            return
        if path == "/export/register.csv":
            name, blob = api.register_csv()
            self._send(200, blob, "text/csv; charset=utf-8",
                       {"Content-Disposition": f'attachment; filename="{name}"'})
            return
        m = re.match(r"^/export/capa/(\d+)\.txt$", path)
        if m:
            name, text = api.capa_report_txt(int(m.group(1)))
            self._send(200, text.encode("utf-8"), "text/plain; charset=utf-8",
                       {"Content-Disposition": f'attachment; filename="{name}"'})
            return
        self._error(404, "Unknown export")

    # -------------------------------------------------------------- static
    def _static(self, rel: str) -> None:
        rel = rel.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
            self._error(404, "Not found")
            return
        ctype, _ = mimetypes.guess_type(full)
        ctype = ctype or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)


# ------------------------------------------------------------------- main

def find_free_port(host: str, preferred: int) -> int:
    for port in [preferred] + [preferred + i for i in range(1, 20)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise SystemExit(f"No free port found near {preferred}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CAPA Web server")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="bind address (default 127.0.0.1; use 0.0.0.0 to share on LAN)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"port (default {DEFAULT_PORT})")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not auto-open a browser window")
    args = parser.parse_args(argv)

    if sys.version_info < (3, 10):
        print("CAPA Web requires Python 3.10 or newer.")
        return 1

    db.init_db()
    port = find_free_port(args.host, args.port)
    server = ThreadingHTTPServer((args.host, port), CapaRequestHandler)
    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{port}/"

    banner = [
        "",
        "  CAPA Web — Corrective & Preventive Action system",
        f"  Server : {url}",
        f"  DB     : {db.DB_PATH}",
        "  Stop   : Ctrl+C",
        "",
    ]
    print("\n".join(banner))

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[capa-web] shutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
