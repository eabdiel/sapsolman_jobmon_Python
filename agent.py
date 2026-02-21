# ======================================================================
#  File......: agent.py
#  Purpose...: Background polling agent (Excel catalog + track_state + snapshot writer).
#  Version...: 0.1.0
#  Date......: 2026-02-21
#  Author....: Edwin Rodriguez (Arthrex IT SAP COE)
# ======================================================================

from __future__ import annotations

import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional, Dict, Any, List, Tuple

import pandas as pd

from snapshot_io import atomic_write_json, read_json, write_json
from sap_api import fetch_jobs_rfc
from sap_connector import connect_sso


DATA_DIR = Path("data")
JOBS_XLSX = DATA_DIR / "jobs.xlsx"
TRACK_STATE = DATA_DIR / "track_state.json"
SNAPSHOT = DATA_DIR / "job_snapshot.json"


def load_job_catalog() -> pd.DataFrame:
    """Load the Excel catalog. This is the long-lived 'what jobs exist' list."""
    df = pd.read_excel(JOBS_XLSX, sheet_name="jobs")
    df.columns = [c.strip().lower() for c in df.columns]

    for col in ["job_name", "job_user", "group"]:
        if col not in df.columns:
            df[col] = ""

    if "expected_duration_sec" not in df.columns:
        df["expected_duration_sec"] = 0
    if "enabled" not in df.columns:
        df["enabled"] = "Y"

    df["job_name"] = df["job_name"].astype(str).str.strip()
    df["job_user"] = df["job_user"].fillna("").astype(str).str.strip()
    df["group"] = df["group"].fillna("").astype(str).str.strip()

    df["expected_duration_sec"] = df["expected_duration_sec"].fillna(0).astype(int)
    df["enabled"] = (
        df["enabled"].fillna("Y").astype(str).str.upper().isin(["Y", "YES", "TRUE", "1"])
    )

    # drop blank job_name rows
    df = df[df["job_name"].str.len() > 0].copy()
    return df


def load_track_state() -> Dict[str, bool]:
    """UI/runtime 'what jobs are tracked right now' state."""
    return read_json(TRACK_STATE, default={})


def save_track_state(state: Dict[str, bool]) -> None:
    write_json(TRACK_STATE, state)


def compute_tracked_jobs(df: pd.DataFrame, track_state: Dict[str, bool]) -> List[Tuple[str, str, int]]:
    """
    Build a list of tracked jobs.
    A job is tracked if:
      - enabled in catalog (Excel)
      - enabled in runtime state (track_state.json)
    """
    tracked: List[Tuple[str, str, int]] = []
    for _, r in df.iterrows():
        name = r["job_name"]
        enabled_catalog = bool(r["enabled"])
        enabled_ui = bool(track_state.get(name, True))
        if enabled_catalog and enabled_ui:
            tracked.append((name, r.get("job_user", ""), int(r.get("expected_duration_sec", 0))))
    return tracked


class AgentController:
    """Controller used by tray app to start/pause/stop the polling thread."""

    def __init__(self, poll_interval_sec: int = 30):
        self.poll_interval_sec = poll_interval_sec
        self.stop_flag = threading.Event()
        self.pause_flag = threading.Event()
        self.thread: Optional[threading.Thread] = None

    def start(self, sap_conn_factory: Optional[Callable[[], Any]] = None) -> None:
        """Start (or resume) the agent."""
        if self.thread and self.thread.is_alive():
            self.pause_flag.clear()
            return

        self.stop_flag.clear()
        self.pause_flag.clear()
        self.thread = threading.Thread(
            target=self._run_loop,
            args=(sap_conn_factory,),
            daemon=True
        )
        self.thread.start()

    def pause(self) -> None:
        self.pause_flag.set()

    def resume(self) -> None:
        self.pause_flag.clear()

    def stop(self) -> None:
        self.stop_flag.set()
        self.pause_flag.clear()

    def _run_loop(self, sap_conn_factory: Optional[Callable[[], Any]]) -> None:
        DATA_DIR.mkdir(exist_ok=True)

        conn = None
        last_catalog_load = 0.0
        df = None

        while not self.stop_flag.is_set():
            if self.pause_flag.is_set():
                time.sleep(0.25)
                continue

            # reload catalog every 60s (Excel edits get picked up without restart)
            if (time.time() - last_catalog_load) > 60 or df is None:
                df = load_job_catalog()
                last_catalog_load = time.time()

            track_state = load_track_state()
            tracked_jobs = compute_tracked_jobs(df, track_state)

            # Connect if/when we switch to RFC
            # if sap_conn_factory and conn is None:
            #     conn = sap_conn_factory()

            # MOCK for now:
            if conn is None:
                conn = connect_sso(system="SMP", client="100", sysnr="00")
            jobs = fetch_jobs_rfc(conn, tracked_jobs)

            snapshot = {
                "meta": {
                    "system": "SMP",
                    "client": "100",
                    "generated_at": datetime.now().astimezone().isoformat(),
                    "poll_interval_sec": self.poll_interval_sec,
                    "tracked_job_count": len(tracked_jobs),
                },
                "jobs": jobs
            }

            atomic_write_json(SNAPSHOT, snapshot)
            time.sleep(self.poll_interval_sec)

        # cleanup
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
