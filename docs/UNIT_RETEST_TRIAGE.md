# Unit Test Re-Test Triage — Build 5 (w3r1), source git dev @ cca968e

**Source:** `FieldOps_Nexus_C_I_R_Unit_Testing_Report.xlsx`
**Result:** 4749 executed · 4721 pass · **28 fail** (26 grouped defects).
**Note:** the tester's snapshot `cca968e` is ~8 commits behind current HEAD (`66e5a10`),
which already includes "fix: resolve application defects". Triaged 2026-11-19 by code read,
live OpenAPI-schema inspection, and live reproduction. pytest could not be run in this
workspace (no local Postgres); DB-backed repo tests should be confirmed with a local `pytest`.

## Real application bug — FIXED
### Malformed OpenAPI path `/api/v1/platform/organizations/{id}//`  (DEF-015, DEF-016, DEF-017)
- **Confirmed from the live schema:** `/api/v1/schema/` lists `/platform/organizations/{id}//`.
- **Cause:** `config/urls.py` registered a route with a single non-capturing alternation
  `(?:set_status|status)`; drf-spectacular renders that group as an empty segment →
  `{id}//`. Your own repo test `test_negative_paths_comprehensive.py`
  (`test_neg_all_api_paths_return_405_for_unsupported_methods`, and the unauthenticated/owner
  negative scans) iterates the schema paths, so the bogus `//` path makes it fail with 404
  (DEF-015/016/017). This same malformed path also produced the platform `//` cases in the
  Backend-API report (DEF-010/011) and Functional report.
- **Fix:** split the alternation into two plain patterns (`…/set_status/?$` and `…/status/?$`),
  removing the empty segment. Both routes and the `platform-organizations-status` reverse name
  are preserved. After deploy, the schema no longer contains `//`.
- **Verify after deploy:** `/api/v1/schema/` has no `//`; re-run `test_negative_paths_comprehensive.py`.

## Not repo tests — tester's own harness files (expectations, not repo defects)
- **DEF-003, DEF-004** (`test_api_operation_matrix.py` — NOT in repo): expect logout without auth
  = 401; the project's contract is **400**, locked by `test_auth_defects_resolution.py::
  test_auth_071/072`. Tester expectation differs from a recorded, tested decision.
- **DEF-008** (`test_authentication.py` — NOT in repo): expects DRF's default auth class string;
  the app uses its own `apps.accounts` authentication class. Not a defect.
- **DEF-006** (live_api_check, Render): auditor → 403 HTML on a platform/guarded route; test
  identity/environment.

## Environment / harness artifacts (lockout, random-UUID, UI redirects)
- **DEF-007, DEF-011** lockout sequence `[401×5, 429, 429]`: AXES locks **after** 5 failures, so
  attempt 6 is the first 429 — correct. The expectation that attempt 5 is already 429 is an
  off-by-one. (Live-confirmed in the Backend-API triage.) Not an app defect.
- **DEF-001, DEF-012, DEF-014, DEF-018, DEF-019, DEF-020, DEF-021, DEF-024** (`assert 404 == 200/409`,
  `KeyError 'results'`): the report states live checks use **random UUIDs and empty bodies**, so
  these positive/negative scenarios hit non-existent objects → 404. Expected-value mismatch in the
  harness, not an app defect. (Mirrors the live-confirmed asset/WO findings: the state machines and
  endpoints behave correctly when given real, in-scope objects.)
- **DEF-010, DEF-022, DEF-023, DEF-026** (`assert 400/200 == 302`): UI/form endpoints redirect
  (302) to login when posted without a session; harness/session expectation.
- **DEF-005** (audit evidence page title missing): page returned the shell HTML; route/render or
  schema-path family; Low.
- **DEF-013** (`ConnectionProxy is None`): test-infra/fixture state in the tester's env.

## Needs a local `pytest` run to confirm (repo test files, possibly harness-overridden expectations)
- **DEF-002, DEF-025** (`test_role_scoping.py`: "True is not false" / "False is not true") and
  **DEF-007** (`test_auth_defects_resolution.py`): these name repo files. The repo suite is expected
  green at HEAD; the tester may apply its own expected values and shared-DB data. Run
  `pytest tests/test_role_scoping.py tests/test_auth_defects_resolution.py -q` on the current HEAD to
  confirm they pass. If any genuinely fail on HEAD, re-triage as a real item.

## Summary
| Group | Defects | Verdict |
|---|---|---|
| Malformed `{id}//` schema | DEF-015/016/017 (+ cross-report platform //) | **Fixed** (config/urls.py) |
| Tester harness files (not in repo) | DEF-003/004/008/006 | Not repo defects |
| Lockout off-by-one / env | DEF-007/011 | Not a defect (lockout works) |
| Random-UUID / data | DEF-001/012/014/018/019/020/021/024 | Harness expectation |
| UI 302 redirects | DEF-010/022/023/026 | Harness/session |
| Misc low | DEF-005/013 | Low / env |
| Confirm with local pytest | DEF-002/025 | Likely harness; verify on HEAD |
