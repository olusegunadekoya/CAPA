"""CAPA Desktop — launcher for Windows PCs.

Double-click this file (or run `python run.py`) to start the application.
Requires Python 3.10+ from python.org (Tkinter is included in the installer).
No third-party packages are needed.
"""
import os
import sys


def main() -> int:
    if sys.version_info < (3, 10):
        print("CAPA Desktop requires Python 3.10 or newer.")
        return 1
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("Tkinter is not available with this Python installation.\n"
              "Reinstall Python from https://www.python.org/downloads/ and keep\n"
              "the 'tcl/tk and IDLE' optional feature checked.")
        return 1
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from capa_app.main import main as app_main
    app_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
