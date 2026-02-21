# ======================================================================
#  File......: sap_api.py
#  Purpose...: SAP job monitoring API layer (mock now, RFC later).
#  Version...: 0.1.0
#  Date......: 2026-02-21
#  Author....: Edwin Rodriguez (Arthrex IT SAP COE)
# ======================================================================

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

# tracked_jobs: List[Tuple[job_name, job_user, expected_duration_sec]]
TrackedJob = Tuple[str, str, int]


def fetch_jobs_mock(tracked_jobs: List[TrackedJob]) -> List[Dict[str, Any]]:
    """
    Mock generator so you can build the UI + tray + JSON loop first.
    Replace later with fetch_jobs_rfc() once your Z RFC exists.
    """
    out: List[Dict[str, Any]] = []
    now = datetime.now().astimezone()

    statuses = ["SCHEDULED", "RUNNING", "OK", "FAILED", "CANCELLED"]
    weights = [0.30, 0.20, 0.35, 0.10, 0.05]

    for job_name, job_user, expected in tracked_jobs:
        status = random.choices(statuses, weights=weights, k=1)[0]

        last_start = None
        last_end = None
        runtime_sec = None
        current_step = ""
        current_step_runtime_sec = None
        steps = []

        next_run = (now + timedelta(minutes=random.choice([5, 15, 30, 60, 120]))).isoformat()

        if status in ("RUNNING", "OK", "FAILED", "CANCELLED"):
            start_dt = now - timedelta(seconds=random.randint(30, 900))
            last_start = start_dt.isoformat()
            runtime_sec = int((now - start_dt).total_seconds())

            # steps
            step_count = random.randint(2, 6)
            running_step = random.randint(1, step_count) if status == "RUNNING" else step_count
            for i in range(1, step_count + 1):
                st = "DONE"
                if status == "RUNNING" and i == running_step:
                    st = "RUNNING"
                steps.append({"step_no": i, "type": "ABAP", "name": f"ZREPORT_{i:02d}", "status": st})

            if status == "RUNNING":
                current_step = f"Step {running_step}/{step_count} - {steps[running_step-1]['name']}"
                current_step_runtime_sec = random.randint(10, max(10, runtime_sec))

            if status != "RUNNING":
                end_dt = start_dt + timedelta(seconds=runtime_sec + random.randint(5, 120))
                last_end = end_dt.isoformat()

        late_by = 0
        if expected and runtime_sec and runtime_sec > expected:
            late_by = runtime_sec - expected

        out.append(
            {
                "job_name": job_name,
                "job_user": job_user,
                "tracked": True,
                "status": status,
                "last_start": last_start,
                "last_end": last_end,
                "next_run": next_run,
                "runtime_sec": runtime_sec,
                "expected_duration_sec": expected,
                "late_by_sec": late_by,
                "current_step": current_step,
                "current_step_runtime_sec": current_step_runtime_sec,
                "steps": steps,
                "last_message": "" if status != "FAILED" else "Mock failure: return code 8",
            }
        )

    return out


def fetch_jobs_rfc(conn, tracked_jobs: List[TrackedJob]) -> List[Dict[str, Any]]:
    """
    RFC version (placeholder).
    Once ABAP Z RFC is ready, this becomes something like:

      payload = {
          "IT_JOB_FILTER": [{"JOBNAME": n, "JOBCOUNT": "", "SDLUNAME": u} for (n,u,_) in tracked_jobs],
          "IV_INCLUDE_STEPS": "X",
          "IV_ONLY_ACTIVE": "",
      }
      resp = conn.call("Z_SRE_JOBMON_EXPORT", **payload)

    Return a list of dicts shaped like fetch_jobs_mock() output.
    """
    raise NotImplementedError("Wire this once Z_SRE_JOBMON_EXPORT is available.")
