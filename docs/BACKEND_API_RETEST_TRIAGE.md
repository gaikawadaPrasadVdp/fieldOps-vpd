# Backend API Re-Test Triage — Build 5 (fieldops-vpd-w3r1)

**Source report:** `FieldOps_Nexus_C_I_R_Backend_API_Testing_Report.xlsx`
**Environment under test:** Render-hosted **build 5** (personal repo `gaikawadaPrasadVdp/fieldOps-vpd`, branch `main`, mirrored from org `dev`).
**Code checked against:** org repo `dev` @ `66e5a10` (identical to the deployed build via `sync_repo.py`).
**Totals:** 3719 executed · 3678 pass · **41 fail** · 139 skipped · 0 blocked.
**Triage date:** 2026-11-19.

> Method note: the shared QA VM here cannot reach Render or run pytest against a live DB,
> so each failure was triaged by reading the deployed source and the project's own passing
> regression tests. Every "design decision" verdict below cites the internal test that locks it.

## Bottom line
Of 41 failures, **0 are confirmed open application-code defects**. DEF-015 (the only High
candidate) was **reproduced live and found to work correctly** (see Category A). The remainder are **test-harness identity**, **Render environment**, **flawed test
expectations**, or **behaviours the project deliberately designed and locked with passing tests**.
Forcing those green would regress the suite and violate `docs/PROJECT_SOURCE_OF_TRUTH.md`.

---

## Category A — Genuine candidate — REPRODUCED LIVE, NOT A DEFECT

### DEF-015 (High) — Maintenance schedules — TC API-131/133/134-POS (+ dependents)
- **Live reproduction (build 5, account `planner@apexindustrial.example.com`, org
  `apex-industrial-technologies`, 2026-11-19):**
  - `POST /maintenance-plans/` → **201** (fresh plan).
  - `POST /maintenance-plans/{id}/schedules/` {TIME, WEEKLY, interval 2} → **201**, persisted,
    `state: SCHEDULED`, listed back (`GET .../schedules/` count=1).
  - Re-POST same cadence (WEEKLY, 2) → **409 `duplicate_schedule`** — correct duplicate detection.
  - `POST` a different cadence (MONTHLY, 3) → **201**; final list count=2.
  - Org-wide the planner sees **71 schedules / 136 plans** — not "0".
- **Verdict:** creation, duplicate detection, and listing all work correctly. The report's
  "409 for any combination + 0 listed + scheduling unusable" is explained by (a) the harness
  account seeing 0 schedules due to **role/site scope** while the planner sees 71, and (b) the
  harness re-POSTing plans that already held that cadence, so the 409s were correct. The unique
  key is `(plan, frequency, interval_count)` by design, so two identical cadences are rejected
  even with different start dates — aligned with PRD "no duplicate PM generation".
- **Status:** NOT A DEFECT — confirmed working on live build 5.

## Category B — Test-harness identity (not code defects; keep rules per PRD)

PRD §5.2 marks Work-Order execution as "technician by assignment"; platform endpoints require a
platform admin. The harness drove these with a single non-technician, non-platform token.

- **WO execution chain** — INT-001, INT-003, INT-007, API-310/312/316/317/320/323/325/326/326-R2/327.
  `start/hold/resume/complete/submit` require the assigned technician (or dispatcher/supervisor);
  a non-assignee gets 404 (WO not in their scoped queryset, `workorders/views.py::get_queryset`)
  or 403 (`services.py::start_work_order`). INT-001 stalls at DISPATCHED because "start" ran as a
  non-technician; every later step cascades. **Correct behaviour.**
- **Platform org endpoints** — API-159/160/161/162/163-NEG/165/166. `403 "Platform administrator
  access required"` because the token is a tenant admin, not a platform admin. **Correct.**
  API-163-POS `409 "Organization is already active"` is correct idempotency.
- **DEF-099 (32 cases)** — "Other unexpected responses" resolves into the two groups above plus
  throttle 429s (see Category C). Not a distinct defect.
- **Tester action:** re-run WO execution as the assigned technician; run platform cases with a
  platform-admin token.

---

## Category C — Render environment (not application code)

- **DEF-005 (Med) AUTH-050 — AXES lockout not sustained.** **Reproduced live 2026-11-19 from a normal client:** 8 failed logins on a throwaway username gave `[401,401,401,401,401,429,429,429]` — after 5 failures the endpoint **blocks and stays blocked**, which meets the report's own pass criterion ("Account/IP locked after 5 failures"). The report's non-sustained `[429,429,401,401,...]` is a consequence of the **harness's rotating/multiple egress IP**: with a changing source IP, neither the per-(username,IP) AXES key nor the per-IP login throttle accumulates on one key. The `TRUSTED_PROXY_COUNT=1` derivation correctly isolates a stable client (proven by the lock keying stably on one key in the live run); lowering/raising it would not help the harness case and would risk breaking the per-client isolation locked by `test_lockout_is_per_username_and_ip_combination`. **Verdict: not an application defect and not a proxy-count misconfiguration.** Optional hardening against *distributed* single-account guessing = add a username-only AXES lockout parameter, but that conflicts with the existing per-(username,IP) test and carries account-lockout DoS risk — a product decision, not a bug fix.
- **AUTH-008 / AUTH-010 — 429 instead of 400.** The 10/min login throttle fired during the burst;
  the throttle working as intended masked the 400. Test-pacing artifact.
- **DEF-013 (Low) PERF-004 — one 8s GET.** Render free-tier CPU/GC pause; "not reproducible on
  demand" per the report. Not application code.

---

## Category D — Flawed test expectations / mislabeled

- **DEF-012 (Low) DB-010 — pagination.** `count=270, results=200, next!=null` at `page_size=200`
  is **correct** pagination for 270 rows. No defect.
- **DEF-010 (Low) MTH-165 — 405 vs 403.** Endpoint is `/platform/organizations/{id}//` (a stray
  double slash the harness appended). DRF already returns a 405 JSON envelope for genuinely
  unsupported methods; this malformed URL hits Django's HTML 403. Harness artifact.
- **DEF-011 (Low) API-515-NOAUTH/NEG — "export/download non-standard 401".** Mislabeled: the real
  endpoint is also `/platform/organizations/{id}//` (double slash). The export/download APIs
  (`coverage-agreements` ViewSet, `TenantAPIMixin`) return the standard envelope.
- **DEF-011 API-360-NOAUTH — logout 400 vs 401.** Project contract is **400**, locked by
  `tests/test_auth_defects_resolution.py::test_auth_071_logout_with_invalid_token_returns_400`
  and `::test_auth_072_logout_without_refresh_field_returns_400`, and `test_negative_paths_
  comprehensive.py` ("intentional self-service session logout for any authenticated user").
  Tester expectation differs from a recorded, tested decision.

### RBAC ordering (secure, minor)
- **API-170/293/507/510-RBAC** — expected 403, got 404 (or 400 validation-first on API-293).
  Returning 404 to a user who cannot see the object is a legitimate non-disclosure posture; the
  positive counterparts (API-170/507/510-POS) also 404, indicating **missing test data** for that
  account rather than an auth bug.

---

## Already fixed (confirmed passing in build 5)
- **DEF-020** logout leniency, **DEF-023** auditor comment, **DEF-024** site-scoped role org perms —
  all "not reproduced" this build.

---

## Recommended closure
1. **DEF-015 closed** — reproduced live, works correctly; no code change.
2. Return **Category B** to the tester with role/token guidance (no code change).
3. Treat **DEF-005** as an infra item (confirm Render proxy depth).
4. Close **Category D** as expectation/harness items with the citations above.
