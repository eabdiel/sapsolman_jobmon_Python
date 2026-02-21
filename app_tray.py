# ======================================================================
#  File......: app_tray.py
#  Purpose...: Windows tray launcher (Start/Pause/Resume/Open Dashboard/Exit).
#  Version...: 0.1.0
#  Date......: 2026-02-21
#  Author....: Edwin Rodriguez (Arthrex IT SAP COE)
# ======================================================================

from __future__ import annotations

import subprocess
import sys
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from agent import AgentController

# If/when you want to wire real SAP:
# from sap_connector import connect_sso
#
# def sap_conn_factory():
#     return connect_sso(system="SMP", client="100", sysnr="00")


BOKEH_URL = "http://localhost:5006/dashboard"
APP_DIR = Path(__file__).resolve().parent


def _make_icon() -> Image.Image:
    """Simple generated tray icon (replace later with .ico if you want)."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((6, 6, 58, 58), radius=12, outline=(255, 255, 255, 255), width=3)
    d.text((18, 22), "JM", fill=(255, 255, 255, 255))
    return img


def _start_bokeh_server():
    """
    Start bokeh serve in a subprocess (v1 approach).
    If it's already running, a second launch will usually fail harmlessly.
    """
    cmd = [
        sys.executable, "-m", "bokeh", "serve",
        "--allow-websocket-origin=localhost:5006",
        "--port", "5006",
        str(APP_DIR / "dashboard.py"),
    ]
    try:
        subprocess.Popen(cmd, cwd=str(APP_DIR))
    except Exception:
        pass


def main():
    agent = AgentController(poll_interval_sec=30)

    def on_start(icon, item):
        _start_bokeh_server()
        agent.start(sap_conn_factory=None)  # mock now

    def on_pause(icon, item):
        agent.pause()

    def on_resume(icon, item):
        agent.resume()

    def on_open(icon, item):
        _start_bokeh_server()
        webbrowser.open(BOKEH_URL)

    def on_exit(icon, item):
        agent.stop()
        icon.stop()

    icon = pystray.Icon(
        "SAP Job Monitor",
        _make_icon(),
        "SAP Job Monitor",
        menu=pystray.Menu(
            pystray.MenuItem("Start", on_start),
            pystray.MenuItem("Pause", on_pause),
            pystray.MenuItem("Resume", on_resume),
            pystray.MenuItem("Open Dashboard", on_open),
            pystray.MenuItem("Exit", on_exit),
        )
    )

    icon.run()


if __name__ == "__main__":
    main()
