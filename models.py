# ======================================================================
#  File......: models.py
#  Purpose...: Dataclasses / models for catalog rows and snapshot records.
#  Version...: 0.1.0
#  Date......: 2026-02-21
#  Author....: Edwin Rodriguez (Arthrex IT SAP COE)
# ======================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class JobCatalogRow:
    job_name: str
    job_user: str = ""
    expected_duration_sec: int = 0
    enabled: bool = True
    group: str = ""


@dataclass
class JobSnapshot:
    job_name: str
    job_user: str
    tracked: bool
    status: str

    last_start: Optional[str] = None
    last_end: Optional[str] = None
    next_run: Optional[str] = None

    runtime_sec: Optional[int] = None
    expected_duration_sec: int = 0
    late_by_sec: Optional[int] = None

    current_step: str = ""
    current_step_runtime_sec: Optional[int] = None

    steps: Optional[List[Dict[str, Any]]] = None
    last_message: str = ""
