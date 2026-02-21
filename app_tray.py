# ======================================================================
#  File......: app_tray.py
#  Purpose...: Windows tray launcher (Start/Pause/Resume/Open/Exit)
#              Can run standalone or be embedded by main.py
#  Version...: 0.3.0
#  Date......: 2026-02-21
#  Author....: Edwin Rodriguez (Arthrex IT SAP COE)
# ======================================================================

from __future__ import annotations

import webbrowser
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw

from agent import AgentController

DASHBOARD_URL = "http://localhost:5006/dashboard"


def set_dashboard_url(url: str) -> None:
    global DASHBOARD_URL
    DASHBOARD_URL = url


def _make_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((6, 6, 58, 58), radius=12, outline=(255, 255, 255, 255), width=3)
    d.text((18, 22), "JM", fill=(255, 255, 255, 255))
    return img


def run_tray(
    on_open: Optional[Callable[[], None]] = None,
    on_exit: Optional[Callable[[], None]] = None,
) -> None:
    agent = AgentController(poll_interval_sec=30)

    def _start(icon, item):
        agent.start()

    def _pause(icon, item):
        agent.pause()

    def _resume(icon, item):
        agent.resume()

    def _open(icon, item):
        if on_open:
            on_open()
        else:
            webbrowser.open(DASHBOARD_URL)

    def _exit(icon, item):
        agent.stop()
        if on_exit:
            on_exit()
        icon.stop()

    icon = pystray.Icon(
        "SAP Job Monitor",
        _make_icon(),
        "SAP Job Monitor",
        menu=pystray.Menu(
            pystray.MenuItem("Start", _start),
            pystray.MenuItem("Pause", _pause),
            pystray.MenuItem("Resume", _resume),
            pystray.MenuItem("Open Dashboard", _open),
            pystray.MenuItem("Exit", _exit),
        ),
    )
    icon.run()


if __name__ == "__main__":
    run_tray()
