# Functional Re-Test Triage — Build 5 (w3r1), report 2026-11-18

**Source:** `FieldOps_Nexus_C_I_R_Functional_Testing_Report_w3r1_2026-11-18.xlsx`
**Result:** 4069 executed · 4066 pass · **3 fail** · 53 skipped.
**Triaged:** 2026-11-19 (code read + live reproduction on build 5).

## DEF-001 (Medium) — TC_M02_124 — "Invalid asset status transition accepted (200)"
- **Verdict: NOT a defect (test-scenario/state error).**
- The scenario sent `complete_maintenance` and expected 400/409, but got 200.
- **Live proof:** on a fresh ACTIVE asset, `complete_maintenance` → **409 `invalid_transition`**
  ("not allowed from state 'ACTIVE'"). Full cycle works: ACTIVE →start→ UNDER_MAINTENANCE
  →complete→ ACTIVE.
- The target asset's own history shows it was moved ACTIVE→UNDER_MAINTENANCE (`start_maintenance`,
  11:37:35) immediately before the test's `complete_maintenance` (11:37:51) — so the transition
  was **valid** when called. The state machine (`assets/workflow.py`) correctly rejects disallowed
  transitions via `StateMachine.apply` → `InvalidTransition`.
- **Action:** none in code. The negative test must assert from a known non-UNDER_MAINTENANCE state.

## DEF-002 (Medium) — TC_AUTH_049 — "No account lockout after repeated failed logins"
- **Verdict: NOT a defect — environment (harness egress IP).** Same as backend-API DEF-005.
- **Live proof:** 8 failed logins from a stable client → `[401,401,401,401,401,429,429,429]`:
  after 5 failures the endpoint blocks and stays blocked, meeting the report's own criterion.
- The report's all-401 run is explained by the harness's rotating/multiple egress IP, so the
  per-(username,IP) AXES key and per-IP throttle never accumulate on one key. The design is locked
  by `tests/test_login_integration.py::test_lockout_is_per_username_and_ip_combination`.
- **Action:** none in code (optional: product decision on username-only lockout; see backend triage).

## DEF-003 (Low) — TC_PUB_001 — "CSP blocks inline event handlers (console errors)"
- **Verdict: REAL defect — FIXED.**
- **Cause:** `src/templates/shell.html` logo `<img>` used an inline `onerror=...` fallback. The
  prior CSP cleanup removed `onclick/onchange/onsubmit` but missed `onerror`. Because `shell.html`
  wraps every `/app/` page, the CSP violation appeared on Dashboard, Sites, Assets, Work Orders.
  Confirmed live: `/app/` logs "Executing inline event handler violates ... script-src 'self'
  'nonce-…'".
- **Fix (CSP-safe, matches the existing delegated-handler pattern):**
  - `shell.html`: inline `onerror` replaced with a `data-img-fallback` marker.
  - `static/js/app.js`: added a capture-phase `error` listener that hides a broken
    `[data-img-fallback]` image and reveals the sibling placeholder.
  - `base.html`: bumped `app.js` asset version `?v=5.0` → `?v=5.1`.
  - Verified: zero inline `on*` handlers remain in any template; `node --check app.js` passes.
- **Deploy note:** the logo also 404s on Render (why `onerror` fires at all) — a static-serving
  item (see `PROJECT_BLOCKER_STATUS.md` Blocker 2, stale `staticfiles`); the fix makes the fallback
  CSP-clean regardless. Re-run `collectstatic`/rebuild on deploy so `?v=5.1` is served.

## Summary
| Defect | Severity | Verdict | Code change |
|---|---|---|---|
| DEF-001 | Medium | Not a defect (test state) | none |
| DEF-002 | Medium | Not a defect (env/harness IP) | none |
| DEF-003 | Low | **Fixed** | shell.html, app.js, base.html |
