
# ======================================================================
#  File......: sap_api.py
#  Purpose...: SAP job monitoring API layer (RFC-enabled)
#  Version...: 0.2.0
#  Date......: 2026-02-21
#  Author....: Edwin Rodriguez (Arthrex IT SAP COE)
# ======================================================================

from __future__ import annotations

from typing import List, Dict, Any, Tuple

TrackedJob = Tuple[str, str, int]


def fetch_jobs_rfc(conn, tracked_jobs: List[TrackedJob]) -> List[Dict[str, Any]]:

    it_filter = []
    expected_map = {}

    for job_name, job_user, expected in tracked_jobs:
        expected_map[job_name] = expected
        it_filter.append({
            "JOBNAME": job_name,
            "SDLUNAME": job_user or "",
            "JOBCOUNT": "",
            "CLIENT": ""
        })

    resp = conn.call(
        "ZSRE_JOBMON_EXPORT",
        IT_FILTER=it_filter,
        IV_ONLY_LATEST="X",
        IV_ONLY_ACTIVE="",
        IV_INCLUDE_STEPS="X",
        IV_MAX_JOBS=200
    )

    et_jobs = resp.get("ET_JOBS", []) or []
    et_steps = resp.get("ET_STEPS", []) or []

    steps_by_key: Dict[tuple, List[Dict[str, Any]]] = {}
    for s in et_steps:
        key = (s.get("JOBNAME", ""), s.get("JOBCOUNT", ""))
        steps_by_key.setdefault(key, []).append({
            "step_no": int(s.get("STEPCNT") or 0),
            "type": s.get("STEP_TYPE", "") or "ABAP",
            "name": s.get("PROGNAME", "") or "",
            "variant": s.get("VARIANT", "") or "",
            "status": s.get("STEP_STATUS", "") or "UNKNOWN",
        })

    out: List[Dict[str, Any]] = []

    for j in et_jobs:
        job_name = (j.get("JOBNAME") or "").strip()
        jobcount = (j.get("JOBCOUNT") or "").strip()

        expected = int(expected_map.get(job_name, 0) or 0)

        runtime_sec = j.get("RUNTIME_SEC")
        try:
            runtime_sec = int(runtime_sec) if runtime_sec not in (None, "") else None
        except Exception:
            runtime_sec = None

        late_by = 0
        if expected and runtime_sec and runtime_sec > expected:
            late_by = runtime_sec - expected

        def dt_str(d, t):
            d = (d or "").strip()
            t = (t or "").strip()
            if len(d) == 8 and d.isdigit():
                yyyy, mm, dd = d[0:4], d[4:6], d[6:8]
                if t and len(t) >= 6 and t.isdigit():
                    hh, mi, ss = t[0:2], t[2:4], t[4:6]
                    return f"{yyyy}-{mm}-{dd}T{hh}:{mi}:{ss}"
                return f"{yyyy}-{mm}-{dd}"
            return None

        last_start = dt_str(j.get("STRTDATE"), j.get("STRTTIME"))
        last_end = dt_str(j.get("ENDDATE"), j.get("ENDTIME"))

        key = (job_name, jobcount)
        steps = steps_by_key.get(key, [])

        status_txt = (j.get("STATUS_TXT") or "").strip() or "UNKNOWN"

        current_step_txt = (j.get("CURRENT_STEP_TXT") or "").strip()
        current_step_no = j.get("CURRENT_STEP_NO")
        try:
            current_step_no = int(current_step_no) if current_step_no not in (None, "") else None
        except Exception:
            current_step_no = None

        current_step = ""
        if current_step_no and current_step_txt:
            current_step = f"Step {current_step_no} - {current_step_txt}"
        elif current_step_txt:
            current_step = current_step_txt

        out.append({
            "job_name": job_name,
            "job_user": (j.get("SDLUNAME") or "").strip(),
            "tracked": True,
            "status": status_txt,
            "raw_status": (j.get("STATUS") or "").strip(),
            "jobcount": jobcount,
            "last_start": last_start,
            "last_end": last_end,
            "next_run": None,
            "runtime_sec": runtime_sec,
            "expected_duration_sec": expected,
            "late_by_sec": late_by,
            "current_step": current_step,
            "current_step_runtime_sec": None,
            "steps": steps,
            "last_message": (j.get("MSG") or "").strip()
        })

    return out
