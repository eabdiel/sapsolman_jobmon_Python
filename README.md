# SAP Job Monitor (ZSRE JobMon)

SAP Solution Manager background job monitoring with Python, Bokeh, PyRFC, and a Windows tray interface for SRE workflows.

A project of **[ProgreTech LLC](https://progretech.com)**, owned and maintained by **Ed Rodriguez**. Third-party components and contributions retain their respective ownership and notices.

[Project website](https://progretech.com) · [Report an issue](https://github.com/eabdiel/sapsolman_jobmon_Python/issues) · [Contribute](CONTRIBUTING.md)

Author: Ed Rodriguez — ProgreTech LLC\
Version: 0.3.0\
System scope: your authorized SAP development or monitoring environment

------------------------------------------------------------------------

## Overview

SAP Job Monitor is a lightweight SRE-oriented monitoring tool that:

-   Connects to SAP via SSO (PyRFC)
-   Calls custom RFC `ZSRE_JOBMON_EXPORT`
-   Polls background job data (SM37 tables TBTCO / TBTCP)
-   Displays live status in a Bokeh dashboard
-   Runs as a Windows system tray application
-   Can be packaged as a single executable

The application is maintained by ProgreTech LLC for SAP SRE workflows and focuses on
visibility, runtime tracking, and operational awareness.

------------------------------------------------------------------------

## Architecture

Single-entry design:

    main.py
     ├─ Starts Bokeh server (in-process)
     ├─ Starts system tray app
     └─ Agent polls SAP via RFC

Key components:

-   `main.py` -- Single entrypoint
-   `app_tray.py` -- Windows tray UI
-   `agent.py` -- Polling controller
-   `sap_api.py` -- RFC call wrapper
-   `sap_connector.py` -- Secure Login Client SSO connection
-   `dashboard.py` -- Bokeh visualization
-   `data/` -- JSON snapshot + Excel tracking list

------------------------------------------------------------------------

## SAP Dependencies

Custom objects required in SAP:

-   Function Module: `ZSRE_JOBMON_EXPORT` (Remote-enabled)
-   Structures:
    -   ZSRES_JOBMON_FILTER
    -   ZSRES_JOBMON_JOB
    -   ZSRES_JOBMON_STEP
-   Table Types:
    -   ZSRET_JOBMON_FILTER
    -   ZSRET_JOBMON_JOB
    -   ZSRET_JOBMON_STEP

Function module reads:

-   TBTCO (job header)
-   TBTCP (job steps)

Raw SAP status is preserved. `STATUS_TXT` is a minimal bucket: -
RUNNING - SCHEDULED - DONE - ERROR - CANCELLED - UNKNOWN

------------------------------------------------------------------------

## Local Setup

Install dependencies:

``` bash
pip install -r requirements.txt
```

Run application:

``` bash
python main.py
```

System tray will appear.\
Use **Start** to begin polling SAP.

Dashboard URL:

    http://localhost:5006/dashboard

------------------------------------------------------------------------

## Excel Tracking

`data/jobs.xlsx` controls which jobs are monitored.

Expected columns:

-   job_name
-   job_user
-   expected_duration_sec
-   tracked (checkbox/flag)

The agent reads this file and sends filters to SAP via RFC.

------------------------------------------------------------------------

## Packaging as Executable

Build single-file Windows executable:

``` bash
pyinstaller --noconsole --onefile main.py
```

Recommended later additions for production packaging:

-   Hidden imports for Bokeh
-   Custom icon
-   Version metadata
-   Windows startup registration

------------------------------------------------------------------------

## Known Limitations (v1)

-   Current step detection is best-effort
-   Next run time not yet exposed
-   Job log extraction not yet implemented
-   No auto-retry logic on RFC disconnect (future enhancement)

------------------------------------------------------------------------

## Future Enhancements

-   Runtime trend sparkline
-   Failure log extraction (TBTC5)
-   Reconnect/backoff logic
-   SLA breach alerting
-   Status badge color in tray icon
-   BTP deployment version (JSON-ready architecture)

------------------------------------------------------------------------

## Collaboration

Sanitized sample data, api compatibility notes, report clarity, and reproducible workflow failures are useful ways to help. Read [CONTRIBUTING.md](CONTRIBUTING.md) for issue reports, proposed changes, and attribution requirements.

## License and reuse

No complete root license was found in this repository. Public availability alone does not grant a general right to reuse or redistribute the code. The maintainer needs to clarify the intended license before code contributions or redistribution.

## More from ProgreTech

Explore [ProgreTech Atlas](https://atlas.progretech.com) for opportunity and evidence research.

Discover the wider portfolio at [progretech.com](https://progretech.com). These links identify related products; they do not imply a bundled integration or shared license.
