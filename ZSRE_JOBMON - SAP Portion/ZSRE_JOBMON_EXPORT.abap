*----------------------------------------------------------------------*
*  FUNCTION MODULE: ZSRE_JOBMON_EXPORT
*----------------------------------------------------------------------*
*  Purpose  : Export SAP background job header + step data (SM37-like)
*             for external monitoring (Python agent / Bokeh dashboard).
*
*  Author   : Edwin Rodriguez (Arthrex IT SAP COE)
*  Version  : 0.1.0
*  Date     : 2026-02-21
*
*  Notes:
*   - Uses standard job tables TBTCO (header) and TBTCP (steps)
*   - Designed for light polling (<= 100 jobs) with optional step export
*   - Status normalization is best-effort; raw STATUS always returned
*   - "Current step" is best-effort; exact step runtime/log parsing is v2
*----------------------------------------------------------------------*
FUNCTION zsre_jobmon_export.
*"---------------------------------------------------------------------
*"*"Local Interface:
*"  IMPORTING
*"     VALUE(IT_FILTER)        TYPE  ZSRET_JOBMON_FILTER
*"     VALUE(IV_ONLY_LATEST)   TYPE  ABAP_BOOL DEFAULT ABAP_TRUE
*"     VALUE(IV_ONLY_ACTIVE)   TYPE  ABAP_BOOL DEFAULT ABAP_FALSE
*"     VALUE(IV_INCLUDE_STEPS) TYPE  ABAP_BOOL DEFAULT ABAP_TRUE
*"     VALUE(IV_MAX_JOBS)      TYPE  INT4 DEFAULT 200
*"  EXPORTING
*"     VALUE(ET_JOBS)          TYPE  ZSRET_JOBMON_JOB
*"     VALUE(ET_STEPS)         TYPE  ZSRET_JOBMON_STEP
*"     VALUE(ET_MESSAGES)      TYPE  BAPIRET2_T
*"---------------------------------------------------------------------

  "------------------------------------------------------------
  " Helpers (local forms)
  "------------------------------------------------------------
  FORM add_msg USING    iv_type   TYPE bapi_mtype
                        iv_id     TYPE symsgid
                        iv_no     TYPE symsgno
                        iv_msgv1  TYPE symsgv
                        iv_msgv2  TYPE symsgv
                        iv_msgv3  TYPE symsgv
                        iv_msgv4  TYPE symsgv.
    DATA ls_ret TYPE bapiret2.
    CLEAR ls_ret.
    ls_ret-type   = iv_type.
    ls_ret-id     = iv_id.
    ls_ret-number = iv_no.
    ls_ret-message_v1 = iv_msgv1.
    ls_ret-message_v2 = iv_msgv2.
    ls_ret-message_v3 = iv_msgv3.
    ls_ret-message_v4 = iv_msgv4.
    APPEND ls_ret TO et_messages.
  ENDFORM.

  "------------------------------------------------------------
  " Input validation
  "------------------------------------------------------------
  CLEAR: et_jobs, et_steps, et_messages.

  IF it_filter IS INITIAL.
    PERFORM add_msg USING 'E' 'ZSRE' '001' 'IT_FILTER is empty' '' '' ''.
    RETURN.
  ENDIF.

  IF iv_max_jobs IS INITIAL OR iv_max_jobs <= 0.
    iv_max_jobs = 200.
  ENDIF.

  IF lines( it_filter ) > iv_max_jobs.
    PERFORM add_msg USING 'E' 'ZSRE' '002' 'Too many filters' |{ lines( it_filter ) }| |Max { iv_max_jobs }| ''.
    RETURN.
  ENDIF.

  "------------------------------------------------------------
  " Authorization check (keep simple; tighten in role config)
  "------------------------------------------------------------
  AUTHORITY-CHECK OBJECT 'S_RFC'
    ID 'RFC_NAME' FIELD 'ZSRE_JOBMON_EXPORT'.
  IF sy-subrc <> 0.
    PERFORM add_msg USING 'E' 'ZSRE' '003' 'No authorization for RFC' 'ZSRE_JOBMON_EXPORT' '' ''.
    RETURN.
  ENDIF.

  "------------------------------------------------------------
  " Normalize filter list (dedupe by JOBNAME + SDLUNAME + JOBCOUNT)
  "------------------------------------------------------------
  DATA lt_filter TYPE zsret_jobmon_filter.
  lt_filter = it_filter.
  SORT lt_filter BY jobname sdluname jobcount.
  DELETE ADJACENT DUPLICATES FROM lt_filter COMPARING jobname sdluname jobcount.

  " Guard for FOR ALL ENTRIES
  IF lt_filter IS INITIAL.
    PERFORM add_msg USING 'E' 'ZSRE' '004' 'No valid filters after normalization' '' '' ''.
    RETURN.
  ENDIF.

  "------------------------------------------------------------
  " Read job headers (TBTCO)
  "------------------------------------------------------------
  DATA: lt_tbtco TYPE STANDARD TABLE OF tbtco WITH DEFAULT KEY.

  SELECT mandt jobname jobcount sdluname status
         strtdate strttime enddate endtime
    FROM tbtco
    INTO TABLE @lt_tbtco
    FOR ALL ENTRIES IN @lt_filter
    WHERE jobname = @lt_filter-jobname
      AND mandt   = @sy-mandt.
  " Note: We intentionally do not filter by SDLUNAME/JOBCOUNT here
  "       because many sites keep JOBCOUNT blank in filters to mean "latest".

  IF sy-subrc <> 0 OR lt_tbtco IS INITIAL.
    PERFORM add_msg USING 'W' 'ZSRE' '010' 'No jobs found in TBTCO for given filters' '' '' ''.
    RETURN.
  ENDIF.

  "------------------------------------------------------------
  " If IV_ONLY_LATEST = 'X':
  "   For each JOBNAME (and optionally SDLUNAME if provided in filter),
  "   pick the max JOBCOUNT.
  "------------------------------------------------------------
  TYPES: BEGIN OF ty_key,
           jobname  TYPE tbtco-jobname,
           sdluname TYPE tbtco-sdluname,
         END OF ty_key.

  DATA: lt_latest TYPE HASHED TABLE OF tbtco
                 WITH UNIQUE KEY jobname sdluname.

  DATA: lt_targets TYPE STANDARD TABLE OF ty_key WITH DEFAULT KEY.
  DATA: ls_key     TYPE ty_key.

  " Build target keys from filter list; if SDLUNAME blank, we'll treat as wildcard
  LOOP AT lt_filter ASSIGNING FIELD-SYMBOL(<f>).
    CLEAR ls_key.
    ls_key-jobname = <f>-jobname.
    ls_key-sdluname = <f>-sdluname.
    APPEND ls_key TO lt_targets.
  ENDLOOP.
  SORT lt_targets BY jobname sdluname.
  DELETE ADJACENT DUPLICATES FROM lt_targets COMPARING jobname sdluname.

  " Helper: function to map status codes to normalized text
  DATA lv_status_txt TYPE char20.
  DATA lv_is_active  TYPE abap_bool.

  " Pre-sort header list to ease max selection
  SORT lt_tbtco BY jobname sdluname jobcount DESCENDING.

  DATA lt_selected TYPE STANDARD TABLE OF tbtco WITH DEFAULT KEY.
  CLEAR lt_selected.

  IF iv_only_latest = abap_true.
    " For each target, select the first matching row (max jobcount due to sort DESC)
    LOOP AT lt_targets INTO ls_key.
      READ TABLE lt_tbtco ASSIGNING FIELD-SYMBOL(<h>)
        WITH KEY jobname = ls_key-jobname
                 sdluname = ls_key-sdluname.
      IF sy-subrc = 0.
        APPEND <h> TO lt_selected.
      ELSE.
        " If SDLUNAME was blank in filter, match any user
        IF ls_key-sdluname IS INITIAL.
          READ TABLE lt_tbtco ASSIGNING <h>
            WITH KEY jobname = ls_key-jobname.
          IF sy-subrc = 0.
            APPEND <h> TO lt_selected.
          ENDIF.
        ENDIF.
      ENDIF.
    ENDLOOP.
  ELSE.
    " Not latest-only: include all rows that match jobname + optional sdluname + optional jobcount
    LOOP AT lt_tbtco ASSIGNING FIELD-SYMBOL(<allh>).
      " check membership against filter list (jobname match + optional sdluname + optional jobcount)
      READ TABLE lt_filter ASSIGNING FIELD-SYMBOL(<ff>)
        WITH KEY jobname = <allh>-jobname
                 sdluname = <allh>-sdluname
                 jobcount = <allh>-jobcount
        BINARY SEARCH.
      IF sy-subrc = 0.
        APPEND <allh> TO lt_selected.
        CONTINUE.
      ENDIF.

      " fallback: filter entries may omit jobcount and/or sdluname
      READ TABLE lt_filter ASSIGNING <ff>
        WITH KEY jobname = <allh>-jobname
        BINARY SEARCH.
      IF sy-subrc = 0.
        IF ( <ff>-sdluname IS INITIAL OR <ff>-sdluname = <allh>-sdluname )
           AND ( <ff>-jobcount IS INITIAL OR <ff>-jobcount = <allh>-jobcount ).
          APPEND <allh> TO lt_selected.
        ENDIF.
      ENDIF.
    ENDLOOP.
  ENDIF.

  IF lt_selected IS INITIAL.
    PERFORM add_msg USING 'W' 'ZSRE' '011' 'No jobs matched selection rules' '' '' ''.
    RETURN.
  ENDIF.

  "------------------------------------------------------------
  " Optionally filter only active jobs
  "------------------------------------------------------------
  IF iv_only_active = abap_true.
    " Keep only likely-active statuses (best-effort)
    DELETE lt_selected WHERE status NOT IN ('R','Y','Z').
  ENDIF.

  IF lt_selected IS INITIAL.
    PERFORM add_msg USING 'I' 'ZSRE' '012' 'No jobs after IV_ONLY_ACTIVE filter' '' '' ''.
    RETURN.
  ENDIF.

  "------------------------------------------------------------
  " Build ET_JOBS (normalize status + compute runtime)
  "------------------------------------------------------------
  DATA: ls_job TYPE zsres_jobmon_job.

  LOOP AT lt_selected INTO DATA(ls_hsel).
    CLEAR: ls_job, lv_status_txt, lv_is_active.

    " Map raw status code -> normalized text (best-effort; adjust for SMP if needed)
    " Common background job status codes vary; raw STATUS is always included.
    CASE ls_hsel-status.
      WHEN 'Z'.               " Active (often)
        lv_status_txt = 'RUNNING'.
        lv_is_active  = abap_true.
      WHEN 'R' OR 'Y'.        " Released / Ready
        lv_status_txt = 'SCHEDULED'.
        lv_is_active  = abap_false.
      WHEN 'F'.               " Finished
        lv_status_txt = 'DONE'.
        lv_is_active  = abap_false.
      WHEN 'A'.               " Aborted
        lv_status_txt = 'ERROR'.
        lv_is_active  = abap_false.
      WHEN 'C'.               " Cancelled (sometimes)
        lv_status_txt = 'CANCELLED'.
        lv_is_active  = abap_false.
      WHEN OTHERS.
        lv_status_txt = 'UNKNOWN'.
        lv_is_active  = abap_false.
    ENDCASE.

    ls_job-jobname   = ls_hsel-jobname.
    ls_job-jobcount  = ls_hsel-jobcount.
    ls_job-sdluname  = ls_hsel-sdluname.
    ls_job-status    = ls_hsel-status.
    ls_job-status_txt = lv_status_txt.
    ls_job-strtdate  = ls_hsel-strtdate.
    ls_job-strttime  = ls_hsel-strttime.
    ls_job-enddate   = ls_hsel-enddate.
    ls_job-endtime   = ls_hsel-endtime.
    ls_job-is_active = lv_is_active.

    " Runtime calculation (seconds) when possible
    DATA: lv_ts_start TYPE timestampl,
          lv_ts_end   TYPE timestampl,
          lv_sec      TYPE int4.

    CLEAR: lv_ts_start, lv_ts_end, lv_sec.

    IF ls_hsel-strtdate IS NOT INITIAL AND ls_hsel-strttime IS NOT INITIAL.
      CONVERT DATE ls_hsel-strtdate TIME ls_hsel-strttime INTO TIME STAMP lv_ts_start TIME ZONE sy-zonlo.
    ENDIF.

    IF ls_hsel-enddate IS NOT INITIAL AND ls_hsel-endtime IS NOT INITIAL.
      CONVERT DATE ls_hsel-enddate TIME ls_hsel-endtime INTO TIME STAMP lv_ts_end TIME ZONE sy-zonlo.
    ENDIF.

    IF lv_ts_start IS NOT INITIAL.
      IF lv_ts_end IS NOT INITIAL.
        " Finished job: start -> end
        lv_sec = cl_abap_tstmp=>subtract( tstmp1 = lv_ts_end tstmp2 = lv_ts_start ).
      ELSE.
        " Running job: start -> now
        GET TIME STAMP FIELD DATA(lv_ts_now).
        lv_sec = cl_abap_tstmp=>subtract( tstmp1 = lv_ts_now tstmp2 = lv_ts_start ).
      ENDIF.
      ls_job-runtime_sec = lv_sec.
    ENDIF.

    " Best-effort message field
    ls_job-msg = ''.
    APPEND ls_job TO et_jobs.
  ENDLOOP.

  "------------------------------------------------------------
  " Steps: Read TBTCP for selected jobs (optional)
  "------------------------------------------------------------
  IF iv_include_steps = abap_true AND et_jobs IS NOT INITIAL.

    DATA lt_tbtcp TYPE STANDARD TABLE OF tbtcp WITH DEFAULT KEY.

    SELECT mandt jobname jobcount stepcnt progname variant authcknam langu
      FROM tbtcp
      INTO TABLE @lt_tbtcp
      FOR ALL ENTRIES IN @et_jobs
      WHERE jobname  = @et_jobs-jobname
        AND jobcount = @et_jobs-jobcount
        AND mandt    = @sy-mandt.

    SORT lt_tbtcp BY jobname jobcount stepcnt ASCENDING.

    DATA ls_step TYPE zsres_jobmon_step.

    LOOP AT lt_tbtcp INTO DATA(ls_s).
      CLEAR ls_step.
      ls_step-jobname  = ls_s-jobname.
      ls_step-jobcount = ls_s-jobcount.
      ls_step-stepcnt  = ls_s-stepcnt.
      ls_step-progname = ls_s-progname.
      ls_step-variant  = ls_s-variant.
      ls_step-authcknam = ls_s-authcknam.
      ls_step-langu    = ls_s-langu.

      ls_step-step_type = 'ABAP'.
      ls_step-step_status = 'UNKNOWN'.
      ls_step-step_text = |{ ls_s-progname } { ls_s-variant }|.

      APPEND ls_step TO et_steps.
    ENDLOOP.

    "----------------------------------------------------------
    " Best-effort CURRENT_STEP assignment for running jobs:
    " - choose the first step (lowest STEPCNT) and mark it RUNNING
    "   because per-step runtime/status isn't reliable from tables alone.
    "----------------------------------------------------------
    LOOP AT et_jobs ASSIGNING FIELD-SYMBOL(<ej>) WHERE status_txt = 'RUNNING'.
      READ TABLE et_steps ASSIGNING FIELD-SYMBOL(<es>)
        WITH KEY jobname = <ej>-jobname jobcount = <ej>-jobcount.
      IF sy-subrc = 0.
        <ej>-current_step_no  = <es>-stepcnt.
        <ej>-current_step_txt = <es>-step_text.

        " Mark the chosen step as RUNNING (best-effort)
        <es>-step_status = 'RUNNING'.
      ENDIF.
    ENDLOOP.

  ENDIF.

  PERFORM add_msg USING 'S' 'ZSRE' '000' 'ZSRE_JOBMON_EXPORT complete' '' '' ''.
ENDFUNCTION.
