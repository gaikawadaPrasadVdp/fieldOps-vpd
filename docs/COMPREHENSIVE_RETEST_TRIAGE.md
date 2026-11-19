# Comprehensive Report Triage & Fixes — 56 local pytest failures

**Source:** `FieldOps_Nexus_Comprehensive_Testing_And_Defect_Analysis_Report.md` (FOPS-QA-REP-2026-11-19).
**Root cause:** commit `274fd3f` ("enhance work order transition handling") added behavior that
bypasses PRD controls and broke 56 pre-existing tests. Verified against the git diff and the PRD.
**Decision:** revert to PRD-canonical (user-approved). pytest could not be run in this workspace;
the user runs it to confirm and iterate.

## Fixes applied to `src/apps/workorders/services.py` (selective revert of 274fd3f regressions;
## the commit's legitimate permission/`can_act` improvements were kept)

### Category A — WO state-machine divergence (32 tests) — FIXED
`services.TRANSITIONS` restored to the canonical PRD lifecycle (matches `workflow.WORK_ORDER_STATUS`,
asserted by `test_defect_fixes_verification.py::test_def_007_state_machines_synchronized`). Removed
the non-canonical edges the commit added: `ASSIGNED→ON_HOLD`, `DISPATCHED→ON_HOLD`,
`IN_PROGRESS→SUPERVISOR_REVIEW`, `ON_HOLD→ASSIGNED/DISPATCHED`.

### Category C — fabricated labor (6 tests) — FIXED
Removed the auto-inserted `1.00`-hour `WorkOrderLabor` records from both `complete_work_order`
("Standard completion labor.") and `submit_for_review` ("Standard resolution labor."). These faked
persistence and defeated the labor-enforcement negative tests; `_check_completion` now correctly
raises `labor_required`. `submit_for_review` from IN_PROGRESS now takes the canonical two-step
(IN_PROGRESS→COMPLETED→SUPERVISOR_REVIEW) and enforces real labor/notes/checklist/evidence.

### Category B — checklist/evidence enforcement (8 tests) — FIXED
In `_check_completion` and `closure_blockers`: checklist validation restored to run via
`validate_for_completion` (a no-op when no checklist is linked, blocks when one is required), and
evidence enforcement restored to **work-type** (`CORRECTIVE`/`INSTALLATION`) instead of the
non-existent `evidence_required` attribute (which was always `False`, disabling evidence blocking).

### Category D — stale portal/role assertions (10 tests) — DEFERRED
Test-only updates (API correctly returns the standard `403` envelope). The current assertions in
`test_portal_auth.py` / `test_role_scoping.py` mostly already check `403`/`permission_denied`, so the
exact stale ones can't be pinpointed without the pytest failure output. Will fix precisely from the
user's `pytest -v` run.

## Verification required (user runs; I can't run pytest here)
```
pytest tests/test_workorder_state_machine_boundaries.py tests/test_defect_fixes_verification.py \
       tests/test_workorder_labor_enforcement.py tests/test_workorder_m08_boundary.py \
       tests/unit_spec/test_part2_sr_wo_insp.py -q
pytest tests/test_portal_auth.py tests/test_role_scoping.py -q   # Category D: share failures
```
Known risk areas to watch in the output: event-sequence assertions on `submit_for_review` (now emits
a `completed` event before `submitted_for_review` when starting from IN_PROGRESS), and any positive
completion test on a CORRECTIVE/INSTALLATION WO that does not attach evidence (now correctly blocked).

## Note on §2 of the source report
Its two "root causes" for earlier QA failures (stale localhost WSGI process; Render build-5 version
lag) are consistent with this session's findings and the other three triage docs.
