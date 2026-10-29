"""CAPA Web — launcher with built-in web server.

Double-click this file (or run `python run_web.py`) to start the CAPA web
application. The built-in HTTP server starts on http://localhost:8765 and a
browser window opens automatically. Requires Python 3.10+ only — no third-party
packages.

Options:
    python run_web.py --port 9000          # different port
    python run_web.py --host 0.0.0.0       # share on your LAN
    python run_web.py --no-browser         # don't auto-open a browser
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    if sys.version_info < (3, 10):
        print("CAPA Web requires Python 3.10 or newer.")
        return 1
    from capa_web.server import main as serve
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
