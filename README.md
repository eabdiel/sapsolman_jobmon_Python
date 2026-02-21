# SAP Job Monitor (Bokeh + PyRFC) — SMP/100

This is a starter kit for a Windows tray-based SAP job monitoring dashboard:
- Tray menu: Start / Pause / Resume / Open Dashboard / Exit
- Agent polls job status and writes a JSON snapshot
- Bokeh dashboard reads the JSON snapshot and renders a live table with filters
- Track checkbox per job persists to `data/track_state.json` (does *not* edit Excel)

## Quick start

1) Install dependencies:
```bash
pip install -r requirements.txt
```

2) Create / update `data/jobs.xlsx` (sheet name must be `jobs`).

Columns:
- job_name (required)
- job_user
- expected_duration_sec
- enabled (Y/N)
- group

3) Run the dashboard:
```bash
bokeh serve --show dashboard.py
```

4) Run the tray app:
```bash
python app_tray.py
```

## Notes

- This repo currently uses **mock job data** (no SAP calls yet).
- Next step is adding ABAP `Z_SRE_JOBMON_EXPORT` + DDIC types and wiring `sap_api.fetch_jobs_rfc()`.
