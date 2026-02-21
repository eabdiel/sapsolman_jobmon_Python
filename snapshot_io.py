# ======================================================================
#  File......: snapshot_io.py
#  Purpose...: JSON read/write helpers (atomic snapshot writes + track_state persistence).
#  Version...: 0.1.0
#  Date......: 2026-02-21
#  Author....: Edwin Rodriguez (Arthrex IT SAP COE)
# ======================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON atomically to avoid partial reads by the dashboard."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default: Any) -> Any:
    """Read JSON safely. Returns default on missing file or parse error."""
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    """Write JSON (non-atomic is fine for small config files like track_state)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
