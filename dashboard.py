# ======================================================================
#  File......: dashboard.py
#  Purpose...: Bokeh server dashboard (live table + filters + track checkbox).
#  Version...: 0.1.0
#  Date......: 2026-02-21
#  Author....: Edwin Rodriguez (Arthrex IT SAP COE)
# ======================================================================

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import (
    ColumnDataSource, DataTable, TableColumn, TextInput, MultiChoice,
    CheckboxEditor, StringFormatter, NumberFormatter, Div, Button, CDSView, BooleanFilter
)

from snapshot_io import read_json, write_json


DATA_DIR = Path("data")
SNAPSHOT = DATA_DIR / "job_snapshot.json"
TRACK_STATE = DATA_DIR / "track_state.json"


def load_track_state() -> Dict[str, bool]:
    return read_json(TRACK_STATE, default={})


def save_track_state(state: Dict[str, bool]) -> None:
    write_json(TRACK_STATE, state)


def load_snapshot() -> Dict[str, Any]:
    return read_json(SNAPSHOT, default={"meta": {}, "jobs": []})


def jobs_to_columns(jobs: List[Dict[str, Any]], track_state: Dict[str, bool]) -> Dict[str, list]:
    cols = {
        "tracked": [],
        "job_name": [],
        "job_user": [],
        "status": [],
        "next_run": [],
        "last_start": [],
        "last_end": [],
        "runtime_sec": [],
        "expected_duration_sec": [],
        "late_by_sec": [],
        "current_step": [],
        "current_step_runtime_sec": [],
        "last_message": [],
        "steps_json": [],
    }

    for j in jobs:
        name = str(j.get("job_name", "")).strip()
        tracked = bool(track_state.get(name, True))
        cols["tracked"].append(tracked)
        cols["job_name"].append(name)
        cols["job_user"].append(j.get("job_user", ""))
        cols["status"].append(j.get("status", ""))
        cols["next_run"].append(j.get("next_run", ""))
        cols["last_start"].append(j.get("last_start", "") or "")
        cols["last_end"].append(j.get("last_end", "") or "")
        cols["runtime_sec"].append(j.get("runtime_sec", None))
        cols["expected_duration_sec"].append(j.get("expected_duration_sec", 0))
        cols["late_by_sec"].append(j.get("late_by_sec", 0))
        cols["current_step"].append(j.get("current_step", ""))
        cols["current_step_runtime_sec"].append(j.get("current_step_runtime_sec", None))
        cols["last_message"].append(j.get("last_message", ""))
        cols["steps_json"].append(j.get("steps", []))

    return cols


# --- UI widgets
title = Div(text="<h2>SAP Job Monitor (SMP/100)</h2>")
meta_div = Div(text="")

search = TextInput(title="Search job name", placeholder="e.g. Z_FI_...")
status_filter = MultiChoice(
    title="Status filter",
    value=[],
    options=["SCHEDULED", "RUNNING", "OK", "FAILED", "CANCELLED"]
)
only_tracked_btn = Button(label="Show tracked only", button_type="default")
show_all_btn = Button(label="Show all", button_type="default")

details = Div(text="<b>Job details</b><br>Select a row to see steps.", width=520)

# --- Data source
snapshot = load_snapshot()
track_state = load_track_state()
source = ColumnDataSource(jobs_to_columns(snapshot.get("jobs", []), track_state))

view = CDSView(filter=BooleanFilter([True] * len(source.data.get("job_name", []))))
show_tracked_only = {"enabled": False}


def apply_filters():
    q = (search.value or "").strip().lower()
    statuses = set(status_filter.value or [])

    tracked_mask = [bool(x) for x in source.data.get("tracked", [])]
    names = [str(x).lower() for x in source.data.get("job_name", [])]
    st = [str(x) for x in source.data.get("status", [])]

    mask = []
    for i in range(len(names)):
        ok = True
        if q and q not in names[i]:
            ok = False
        if statuses and st[i] not in statuses:
            ok = False
        if show_tracked_only["enabled"] and not tracked_mask[i]:
            ok = False
        mask.append(ok)

    view.filter = BooleanFilter(mask)


def refresh_from_snapshot():
    snap = load_snapshot()
    meta = snap.get("meta", {})
    jobs = snap.get("jobs", [])

    ts = meta.get("generated_at", "")
    poll = meta.get("poll_interval_sec", "")
    count = meta.get("tracked_job_count", "")
    meta_div.text = (
        f"<b>Last refresh:</b> {ts} &nbsp; | &nbsp; "
        f"<b>Poll:</b> {poll}s &nbsp; | &nbsp; "
        f"<b>Tracked (agent):</b> {count}"
    )

    state = load_track_state()
    source.data = jobs_to_columns(jobs, state)
    apply_filters()


# --- Table columns
columns = [
    TableColumn(field="tracked", title="Track", editor=CheckboxEditor(), width=60),
    TableColumn(field="job_name", title="Job", width=220),
    TableColumn(field="job_user", title="User", width=90),
    TableColumn(field="status", title="Status", width=90),
    TableColumn(field="next_run", title="Next Run", width=160, formatter=StringFormatter()),
    TableColumn(field="last_start", title="Last Start", width=160),
    TableColumn(field="last_end", title="Last End", width=160),
    TableColumn(field="runtime_sec", title="Runtime (s)", width=95, formatter=NumberFormatter(format="0")),
    TableColumn(field="expected_duration_sec", title="Expected (s)", width=100, formatter=NumberFormatter(format="0")),
    TableColumn(field="late_by_sec", title="Late By (s)", width=90, formatter=NumberFormatter(format="0")),
    TableColumn(field="current_step", title="Current Step", width=260),
]

table = DataTable(
    source=source,
    columns=columns,
    view=view,
    editable=True,
    index_position=None,
    width=1400,
    height=520,
    autosize_mode="fit_columns"
)


def on_source_data_change(attr, old, new):
    """Persist Track checkbox edits into track_state.json."""
    try:
        names = source.data.get("job_name", [])
        tracked = source.data.get("tracked", [])
        state = load_track_state()
        for n, t in zip(names, tracked):
            if n:
                state[str(n)] = bool(t)
        save_track_state(state)
        apply_filters()
    except Exception:
        pass


source.on_change("data", on_source_data_change)


def on_selection_change(attr, old, new):
    if not new:
        details.text = "<b>Job details</b><br>Select a row to see steps."
        return

    i = new[0]
    job = source.data["job_name"][i]
    status = source.data["status"][i]
    last_start = source.data["last_start"][i]
    runtime = source.data["runtime_sec"][i]
    current_step = source.data["current_step"][i]
    msg = source.data["last_message"][i]
    steps = source.data["steps_json"][i] or []

    steps_html = "<ul>"
    for s in steps:
        steps_html += f"<li>Step {s.get('step_no')} - {s.get('name')} ({s.get('status')})</li>"
    steps_html += "</ul>"

    details.text = (
        f"<b>{job}</b><br>"
        f"<b>Status:</b> {status}<br>"
        f"<b>Last start:</b> {last_start}<br>"
        f"<b>Runtime:</b> {runtime}<br>"
        f"<b>Current step:</b> {current_step}<br>"
        f"<b>Message:</b> {msg}<br><br>"
        f"<b>Steps</b>{steps_html}"
    )


table.source.selected.on_change("indices", on_selection_change)


def on_filters_change(attr, old, new):
    apply_filters()


search.on_change("value", on_filters_change)
status_filter.on_change("value", on_filters_change)


def show_tracked():
    show_tracked_only["enabled"] = True
    apply_filters()


def show_all():
    show_tracked_only["enabled"] = False
    apply_filters()


only_tracked_btn.on_click(show_tracked)
show_all_btn.on_click(show_all)

controls = row(search, status_filter, only_tracked_btn, show_all_btn)
layout = column(title, meta_div, controls, row(table, details))

curdoc().add_root(layout)
curdoc().title = "SAP Job Monitor"
curdoc().add_periodic_callback(refresh_from_snapshot, 2000)
