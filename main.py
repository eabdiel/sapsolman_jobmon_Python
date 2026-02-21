# ======================================================================
#  File......: main.py
#  Purpose...: Single entrypoint to run Bokeh server + Tray app together
#  Version...: 0.3.0
#  Date......: 2026-02-21
#  Author....: Edwin Rodriguez (Arthrex IT SAP COE)
# ======================================================================

from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.script import ScriptHandler

import app_tray

APP_DIR = Path(__file__).resolve().parent
DASHBOARD_SCRIPT = str(APP_DIR / "dashboard.py")


def _start_bokeh_server() -> Server:
    handler = ScriptHandler(filename=DASHBOARD_SCRIPT)
    app = Application(handler)

    server = Server(
        {"/dashboard": app},
        port=5006,
        allow_websocket_origin=["localhost:5006"],
    )

    server.start()
    threading.Thread(target=server.io_loop.start, daemon=True).start()
    return server


def main():
    server = _start_bokeh_server()

    app_tray.set_dashboard_url("http://localhost:5006/dashboard")

    app_tray.run_tray(
        on_open=lambda: webbrowser.open("http://localhost:5006/dashboard"),
        on_exit=lambda: server.io_loop.stop(),
    )


if __name__ == "__main__":
    main()
