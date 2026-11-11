# FieldOps Nexus — Functional Testing Resolution & Verification Report

This report covers **two QA rounds** executed against the internal Render deployment:

- **Round 2 — 2026-11-10:** [`FieldOps_Nexus_Complete_Functional_Testing_I-R.xlsx`](https://docs.google.com/spreadsheets/d/1FEtI5lAu0h2LO6ju8PWloSFV8uC0c2Ln/edit?gid=2098679145#gid=2098679145) (`https://fieldops-qry5.onrender.com`) — 3,644 cases → see §R2 below.
- **Round 1 — 2026-11-09:** same workbook family (`https://fieldops-vpd-yrrh.onrender.com`) — 3,534 cases → archived in §R1 at the bottom.

- **Target Repository / Branch:** `c:\f\FieldOps_Nexus_Internal` (`fix/api`)

---

# Round 2 — Complete Functional Testing (2026-11-10)

- **Source Report:** `FieldOps_Nexus_Complete_Functional_Testing_I-R.xlsx` (3,644 prepared cases; UI + API + business workflow)
- **Target Environment:** `https://fieldops-qry5.onrender.com` (internal Render deployment, Chromium)
- **Verification Date:** 2026-11-11
- **Result:** 3,491 PASS · 8 FAIL · 78 BLOCKED · 67 SKIPPED (3,499 executed)

## R2.1 Executive Summary (3,644 Total Excel Cases)

| Excel Status | Excel Count | Completed in Local Code (`fix/api`) | Pending Code Fix | Pending Outside Code (Deploy / QA Data / Decision) |
|---|---:|---:|---:|---|
| **`PASS`** | **3,491** | **3,491** | 0 | — |
| **`FAIL`** (`DEF-001`–`DEF-004`) | **8** | **8** | 0 | Deploy + re-verify on Render (`8`) |
| **`BLOCKED`** *(defect-blocked dashboard snapshots)* | **2** | **2** | 0 | Deploy + re-verify on Render (`2`) |
| **`BLOCKED`** *(QA DB / test data / script)* | **76** | — | 0 | Clean Render QA fixtures / script (`76`) |
| **`SKIPPED`** *(QA role / console mismatch)* | **56** | — | 0 | Use standard Client role / Admin console (`56`) |
| **`SKIPPED`** *(spec / design ambiguities)* | **10** | — | 0 | Optional product decisions only (`10`) |
| **`SKIPPED`** *(deploy lag — endpoint exists in `fix/api`)* | **1** | **1** | 0 | Deploy + re-verify on Render (`1`) |
| **Total** | **3,644** | **3,502** | **0** | **86** *(not code bugs)* + **11** *(awaiting Render deploy)* |

### Bottom Line

- **Completed in current code:** **`3,502 / 3,644`** — all `3,491` passing cases plus every **`8/8` FAIL** case, both defect-blocked cases, and the deploy-lagged logout case (`/api/v1/auth/logout/` already exists in `fix/api`; the QA instance simply predates it).
- **Pending code bug fixes:** **`0`**.
- **One additional defect found during verification (not in the QA register):** `E2E_023`'s HTTP 500 was classified by QA as a test-precondition issue, but local reproduction proved it is a real code bug — `POST /work-orders/{id}/complete/` with the documented `{"summary": ...}` payload crashed with `TypeError` (500). Fixed and covered by a regression test (see `R2-DEF-005`).
- **Pending before Render QA reaches 100% (`153` non-PASS rows):**
  1. **Deploy & run migrations on Render (`11` cases):** fixes live on local `fix/api` and require deploy + migrations (`dashboards/0003`, `core/0006`) to take effect.
  2. **QA environment & test-data setup (`76 BLOCKED`):** shared Render DB state (fixture safety, technician `max_active_jobs` saturation, empty collections, Playwright script gaps).
  3. **QA test-role setup (`56 SKIPPED`)** and **`10` documented ambiguities** left as-is to preserve existing functionality and tests.

## R2.2 The 8 `FAIL` Cases (4 Registered Defects) — Resolved in Code

| Defect | Cases | Severity | Summary & Code Resolution |
|---|---:|---|---|
| **DEF-001** | 2 | MEDIUM | **Dashboard snapshot endpoints return HTTP 500 (`GET/POST /dashboards/snapshots/`):** The Render database was missing columns created by earlier local migrations (schema drift between the deployed build and `fix/api`). Added an idempotent repair migration `src/apps/dashboards/migrations/0003_fix_snapshot_schema.py` that adds any missing columns/defaults before the snapshot views read them, so the endpoints answer `200` (list), `201` (create) and `404` JSON (unknown id) regardless of prior drift. (`TC_M14_013`, `TC_M14_033`) |
| **DEF-002** | 1 | MEDIUM | **No login throttling on the JWT endpoint (documented 10/min):** The throttle counter silently degraded to per-process memory when `REDIS_URL` was absent, so the single-worker QA instance still enforced nothing after restarts and 13 rapid bad logins were all answered `401`. Added a shared `login_throttle` cache alias in `src/config/settings/base.py` (Redis when configured, otherwise the `core_login_throttle` database table via new migration `src/apps/core/migrations/0006_create_login_throttle_cache.py`) and hardened `ClientIPScopedRateThrottle` in `src/apps/accounts/api.py` to count against the shared store with a per-process fallback that degrades open if every backend fails (a cache outage must never take authentication down). Verified locally: 13 bad logins → `[401 ×10, 429, 429, 429]`. (`TC_AUTH_055`) |
| **DEF-003** | 4 | LOW | **OpenAPI response drift:** (a) *Incidents downtime:* `GET /service-requests/{id}/downtime/` answered `200` with a `null` body when no downtime record existed, violating the documented object schema — now raises `404` with the standard error envelope (`apps.core.exceptions.NotFound`) and the schema documents the `404` (`src/apps/incidents/api_views.py`). (b) *Client portal:* `GET /portal/requests/{id}/` dropped the `work_order` key entirely while unlinked, contradicting the nullable documented field — the key is now always present (`null` = not linked yet; `src/apps/portal/api_views.py`). (`TC_M05_050`, `TC_M05_131`, `TC_M13_083`, `TC_M13_089`) |
| **DEF-004** | 1 | MEDIUM | **Inspection requirements endpoint returns HTTP 500:** `GET /inspections/requirements/` raised `NameError` (`PermissionDenied` was referenced without being imported) in `src/apps/checklists/api_views.py`. Import added; endpoint now returns `200` (owner), `400` (missing `work_order` parameter) and `403` (portal client) with the standard envelope. (`TC_M08_085`) |
| **R2-DEF-005** *(found during verification)* | 1 *(was BLOCKED)* | MEDIUM | **Work order completion with `summary` returns HTTP 500 (`E2E_023`):** QA's blocked-register entry blamed a technician precondition, but reproduction showed a real crash: `WorkOrderCompleteSerializer` accepted the documented `summary` alias, mapped it to `resolution_notes`, but left it in `validated_data`, and the view forwards `**validated_data` to `complete_work_order()` → `TypeError`. Fixed by popping the alias after mapping in `src/apps/workorders/serializers.py`. Completion now succeeds with `{"summary": ...}` (alias) or `{"resolution_notes": ...}`, and precondition failures keep returning `409` (`checklist_incomplete` / `labor_required`) instead of a 500. |

## R2.3 All 78 `BLOCKED` Cases — Full Breakdown

### R2.3A. Resolved in Code (2 Cases — unblocked once deployed)

- `TC_M14_016` (auditor `POST /dashboards/snapshots/`), `TC_M14_018` (`GET /dashboards/snapshots/{id}/` valid identifier) — collateral of the dashboard snapshot defect (the QA sheet labels it "DEF-004"; the defect register maps the snapshot 500s to `DEF-001`). With `dashboards/0003` applied the auditor gets the proper permission response and snapshots can be created and retrieved. Covered by `tests/test_excel_defects_round2_regression.py`.

### R2.3B. Render QA Environment / Test-Data Preconditions — Not Code Defects (76 Cases)

- **27 cases (technician `max_active_jobs` / workflow precondition):** `TC_M06_{016,021,036,046,051,066,071,081,086,101,111,116,117,122}`, `TC_M07_{068,073,091,100,118,127,137,142,147}`, `TC_E2E_{001,004,005,016}` and `TC_E2E_023` (whose 500 had a real code cause — see `R2-DEF-005`, now fixed) — the shared QA technician account had already reached `max_active_jobs = 3`, so assignment-dependent cases could not reach the state under test.
- **28 cases (no safe disposable fixture on the shared Render DB):** `TC_AUTH_{001,008,011}`, `TC_M01_028`, `TC_M05_071`, `TC_M11_{013,029,052,068}`, `TC_M13_{062,073,090,095,100,105}`, `TC_M07_{006,011,021,031,036,045}`, `TC_INTG_{011,021,026,035}` — destructive/precondition cases that could not be run safely against shared state.
- **10 cases (empty collections on the shared QA DB):** `TC_M07_{041,060,064,078,082,096,105,114,123}`, `TC_INTG_031` — no records existed to retrieve.
- **9 cases (`Dependent on POS case`, schema validation):** `TC_M08_089`, `TC_M10_{055,082,144,171}`, `TC_M13_022`, `TC_M14_023`, `TC_M15_{012,018}` — a positive-path 200 (or documented schema) is required before the negative-path schema check can run.
- **1 case (browser harness exception):** `TC_AUTH_071` — Chromium aborted the logout navigation (`ERR_ABORTED`), a Playwright artifact.
- **1 case (Playwright cascading dropdown script):** `TC_M01_357` — Country → State → City dependent selects work in application code (`src/apps/sites/forms.py`, `src/static/js/app.js`); the QA script did not drive the dependent events.

## R2.4 All 67 `SKIPPED` Cases — Breakdown

- **25 cases (`TC_IDRBAC_209`–`233`):** Platform Super Admin uses a separate admin console rather than tenant `/app/*` navigation expectations.
- **31 cases (QA client account custom role):** `TC_IDRBAC_{193,194,195,396}`–`TC_IDRBAC_419`, `TC_M06_148`, `TC_M08_152`, `TC_M09_302`, `TC_M13_126` — the shared QA client user held a custom site-scoped role instead of the standard Client template.
- **10 intentional / documented ambiguities (left unchanged to preserve existing features & tests):**
  1. `TC_AUTH_052`: 7 consecutive bad logins all `401` — **correct**: the JWT endpoint limit is `10/min` (7 < 10); the 5-failure `django-axes` lockout applies to the web login only.
  2. `TC_M13_101`, `TC_M13_106` (`POST /portal/requests/{id}/reopen[/]`): serializer body validation (`reason` required → `400`) executes before the `404` object lookup.
  3. `TC_M06_130` (`POST /work-orders/{id}/transition/`): empty body validates `action` (`400`) before action-specific RBAC (`403`).
  4. `TC_M10_018`, `TC_M10_241`: repetitive-text validator rejects duplicate descriptions.
  5. `TC_M05_178`: intentional `validate_alphabetical_description` rejects digits in incident titles.
  6. `TC_M14_030`: reversed `from`/`to` dates are normalized to a 31-day window ending at `to`.
- **1 case (deploy lag — endpoint exists in `fix/api`):** `TC_AUTH_051` (`POST /auth/logout/`) — `LogoutView` is implemented and routed at `/api/v1/auth/logout/` in this branch (refresh-token blacklist); the QA instance was built from an older commit. Resolves on deploy.

## R2.5 Local Verification Results

- **Excel Round-2 Defect Regression Suite (`tests/test_excel_defects_round2_regression.py`):** **10/10 passed** — covers `DEF-001` (healthy-schema no-op + drift-restore simulation), `DEF-002` (cache wiring, shared-store enforcement, cross-cache sharing, total counter-store outage degrades open), `DEF-003a` (404 envelope + schema), `DEF-003b` (`work_order` always present), `DEF-004` (full 200/400/403 contract) and `E2E_023`/`R2-DEF-005` (completion with `summary`, plus the `409 checklist_incomplete` precondition path).
- **End-to-end reproduction script** (direct HTTP against a migrated local Postgres): all four registered defects verified fixed — snapshots `200/201/404`; 13 bad logins → `[401 ×10, 429, 429, 429]`; downtime `404` envelope (and `200` with a record); portal `work_order` `null` (unlinked) / dict (linked); inspection requirements `200/400/403`; work order completion with `{"summary": ...}` → `200`.
- **Pending Migrations Check (`manage.py makemigrations --check --dry-run`):** **"No changes detected"** — the two new migrations are complete and consistent with the models.
- **Lint (`ruff check` over all files touched by this round):** clean (remaining repo-wide findings are pre-existing at `HEAD` and untouched by these fixes).
- **Django Test Suite (`python -m pytest -q`, full run 27:39):** **1,236 / 1,236 non-browser tests pass** (1,235 passed in the run + the one portal contract test updated below), including the 10 new round-2 regression tests, the round-1 regression suite, and the negative-path suite.
  - The run also executes the 105 Playwright browser tests in `tests/qa_playwright/` (93 failed + 12 errors) — these require a live dev server on `127.0.0.1:8000`, are environmental, and are excluded from verification exactly as in Round 1.
  - *One pre-existing test codified the DEF-003b drift:* `tests/test_portal_request_tracking.py::test_sensitive_internal_fields_excluded` asserted `work_order` was absent from the portal detail payload. It was updated to assert the fixed contract (`work_order` always present, `null` while unlinked); every genuinely sensitive key (`internal_notes`, `technician`, `assigned_to`, `work_orders`, `audit_metadata`) remains excluded. **22/22 tests in the affected files pass after the update.**

## R2.6 Deployment Checklist for Live Render Verification

1. Deploy branch `fix/api` to `https://fieldops-qry5.onrender.com` (the QA build predates this branch — it lacks both the previous 15 commits and this round's fixes, which also explains `TC_AUTH_051`).
2. Run `python manage.py migrate` (Render start script does this via `RUN_MIGRATIONS_ON_START=true`) to apply:
   - `dashboards/0003_fix_snapshot_schema.py` (DEF-001 repair)
   - `core/0006_create_login_throttle_cache.py` (DEF-002 shared throttle counters)
3. Ensure `REDIS_URL` is set (preferred) — the login throttle automatically falls back to the shared database table when it is not.
4. Re-run QA using:
   - A technician account with fewer than 3 active jobs (`max_active_jobs = 3`)
   - Standard Client role credentials for client RBAC checks
   - Seeded records for the empty collections (`/technician-profiles/`, `/webhooks/`, …)
   - Safe disposable fixtures instead of shared-state assumptions
   - Dependent `<select>` event triggers for Country → State → City in Playwright (`/app/sites/`)

---

# Round 1 (Archive) — 2026-11-09

- **Source Report:** [FieldOps_Nexus_Complete_Functional_Testing_I-R.xlsx](https://docs.google.com/spreadsheets/d/1FEtI5lAu0h2LO6ju8PWloSFV8uC0c2Ln/edit?gid=2098679145#gid=2098679145)
- **Target Repository / Branch:** `c:\f\FieldOps_Nexus_Internal` (`fix/api`)
- **Verification Date:** 2026-11-09

---

## 1. Executive Summary (3,534 Total Excel Cases)

| Excel Status | Excel Count | Completed in Local Code (`fix/api`) | Pending Code Fix | Pending Outside Code (Deploy / QA Data / Decision) |
|---|---:|---:|---:|---|
| **`PASS`** | **3,308** | **3,308** | 0 | — |
| **`FAIL`** (`DEF-001`–`DEF-015`) | **90** | **90** | 0 | Deploy + re-verify on Render (`90`) |
| **`BLOCKED`** *(defect / OpenAPI schema)* | **20** | **20** | 0 | Deploy + re-verify on Render (`20`) |
| **`BLOCKED`** *(QA DB / test data / script)* | **52** | — | 0 | Clean Render QA fixtures / script (`52`) |
| **`SKIPPED`** *(QA role / console mismatch)* | **55** | — | 0 | Use standard Client role / Admin console (`55`) |
| **`SKIPPED`** *(spec / design ambiguities)* | **9** | — | 0 | Optional product decisions only (`9`) |
| **Total** | **3,534** | **3,418** | **0** | **116** *(not code bugs)* + **110** *(awaiting Render deploy)* |

### Bottom Line

- **Completed in current code:** **`3,418 / 3,534`** (`3,308` already passing + **`110 / 110`** code and OpenAPI schema issues fixed: all **`90` `FAIL`** cases and all **`20`** code/schema **`BLOCKED`** cases).
- **Pending code bug fixes:** **`0`**.
- **Pending before Render QA shows 100% completion (`226` non-PASS rows in the static report):**
  1. **Deploy & run migrations on Render (`110` cases):** Fixes exist in local branch `fix/api` and must be deployed + migrated (`maintenance/0007`, `dashboards/0002`, `workspace/0004`) to take effect on `https://fieldops-vpd-yrrh.onrender.com`.
  2. **QA environment & test-data setup (`52 BLOCKED`):** Shared Render DB state / empty seeded collections / Playwright cascading-select automation (not code defects).
  3. **QA test-role setup & optional spec items (`64 SKIPPED`):** `55` QA role/console mismatches and `9` intentional/optional product behaviors left intact so existing functionality and tests are preserved.

---

## 2. All 90 `FAIL` Cases (`DEF-001`–`DEF-015`) — Resolved in Code

| Defect | Cases | Severity | Summary & Code Resolution |
|---|---:|---|---|
| **DEF-001** | 2 | HIGH | **PM schedule `409 duplicate_schedule`:** Updated `src/apps/maintenance/services.py` (`_is_duplicate_schedule_error`) so only real schedule uniqueness conflicts raise `409`, paired with schema reconciliation migration `src/apps/maintenance/migrations/0007_reconcile_legacy_columns.py`. (`TC_M04_056`, `TC_E2E_009`) |
| **DEF-002** | 6 | HIGH | **Invite / resend / platform user creation `500`:** Wrapped broker dispatch in `transaction.on_commit` with exception-safe helpers in `src/apps/accounts/services.py` (`_safe_delay_invitation`) and `src/apps/notifications/services.py` (`_safe_delay_notification`); bounded combined names (`[:150]`), normalized blank passwords to `None`, and validated `org_id` UUIDs in `src/apps/tenancy/api_views.py` (`PlatformUserViewSet.create`). (`TC_IDRBAC_{007,033,088,114}`, `TC_PLAT_{027,031}`) |
| **DEF-003** | 1 | MEDIUM | **Organization delete `500`:** Imported `ValidationError`, added missing dependent tables, checked table existence via `connection.introspection.table_names`, and wrapped portal auto-grants in savepoints in `src/apps/tenancy/services.py` (`permanently_delete_organization`). (`TC_PLAT_010`) |
| **DEF-004** | 5 | MEDIUM | **Dashboard snapshots `500`:** Added `src/apps/dashboards/migrations/0002_sync_schema.py` and schema annotations on `SnapshotListAPIView` / `SnapshotDetailAPIView` in `src/apps/dashboards/api_views.py`. (`TC_M14_{007,013,019,032,033}`) |
| **DEF-005** | 1 | MEDIUM | **5,000-char email login `500`:** Added `MaxLengthValidator(254)` in `src/apps/accounts/api.py` (`BoundedTokenObtainPairSerializer`) and sliced keys `[:254]` in `src/apps/core/net.py` (`axes_username`) before `django-axes` queries the DB. (`TC_AUTH_026`) |
| **DEF-006** | 1 | MEDIUM | **JWT login rate limiting:** Enabled `ClientIPScopedRateThrottle` (`10/min` on login/refresh with `NUM_PROXIES` and fallback `LocMemCache`) in `src/apps/accounts/api.py` and `src/config/settings/base.py`. (`TC_AUTH_052`) |
| **DEF-007** | 1 | MEDIUM | **Parts UI alphanumeric/unit validation:** Allowed alphanumeric characters and standard separators (`-./#_ `) for `part_number` and `unit` in `src/apps/inventory/forms.py` (`PartForm`) and `src/templates/ui/form_page.html`. (`TC_M09_365`) |
| **DEF-008** | 1 | MEDIUM | **Job defect report `500`:** Added `src/apps/workspace/migrations/0004_ensure_worknote_table.py` and standardized error payload structure in `src/apps/workspace/api_views.py` (`JobReportDefectAPIView`). (`TC_M07_024`) |
| **DEF-009** | 1 | MEDIUM | **Technician detail route `404` for list `id`:** Updated `_resolve_technician_membership` in `src/apps/workspace/api_views.py` to resolve either `TechnicianProfile.pk` or `Membership.pk`. (`TC_M07_185`) |
| **DEF-010** | 1 | MEDIUM | **Asset UI name `>200` chars silent truncation:** Removed HTML `maxlength` truncation in `src/apps/assets/forms.py` (`AssetForm.__init__`) and added client-side `<= 200` validation in `src/static/js/app.js` (`initAssetForm`) matching the API limit. (`TC_M02_285`) |
| **DEF-011** | 40 | LOW | **Unsupported HTTP methods return `403` instead of `405`:** Checked `action_map` / `allowed_methods` and raised `MethodNotAllowed` (`405`) before permissions in `src/apps/tenancy/api.py` (`TenantAPIMixin.initial`), and removed unimplemented `"put"` entries from `ShiftDetailAPIView` / `TechnicianProfileDetailAPIView` in `src/apps/workspace/api_views.py`. (`TC_M07_161`–`184`, `TC_M11_223`, `TC_M13_110`–`120`, `TC_M14_035`–`038`) |
| **DEF-012** | 24 | LOW | **OpenAPI 200 schema & nullability drift:** Added `src/apps/core/schema.py` (`FieldOpsAutoSchema`) and aligned serializers/`@extend_schema` annotations across `assets`, `checklists`, `maintenance`, `workorders`, `inventory`, `contracts`, `portal`, `incidents`, `dashboards`, `workspace`, and `audit`. |
| **DEF-013** | 4 | LOW | **Unauthenticated export/download `401` plain text:** Updated `PassthroughRenderer.render` in `src/apps/contracts/api_views.py` to serialize error dicts/lists as `application/json; charset=utf-8`. (`TC_M10_{052,079,141,168}`) |
| **DEF-014** | 1 | LOW | **Unused path parameters in Swagger:** Implemented `_get_parameters` and `strip_unused_path_parameters` in `src/apps/core/schema.py`, wired via `src/config/settings/base.py`. (`TC_M02_211`) |
| **DEF-015** | 1 | MEDIUM | **Issuing parts directly from `REQUESTED`:** Enforced `409 Conflict` (`code="reservation_required"`) in `src/apps/inventory/services.py` (`issue`) and hid the UI `Issue` button while `REQUESTED` in `src/apps/inventory/views.py` (`line_ops`). (`TC_M09_238`) |

---

## 3. All 72 `BLOCKED` Cases — Full Breakdown

### 3A. Resolved in Code & OpenAPI Schema (20 Cases)

1. **Explicitly defect-blocked (7 cases):**
   - `TC_M04_072`, `TC_M04_082`, `TC_M04_087`, `TC_M04_092`, `TC_M04_093` (unblocked by `DEF-001`)
   - `TC_M14_016`, `TC_M14_018` (unblocked by `DEF-004`)
   - Verified end-to-end in `tests/test_excel_defects_regression.py`.
2. **M04 empty-collection reads caused by `DEF-001` (3 cases):**
   - `TC_M04_013`, `TC_M04_067`, `TC_M04_077` — verified returning HTTP `200` once PM schedules/cycles exist.
3. **OpenAPI 200 schema validations (`Dependent on POS case`, 10 cases):**
   - `TC_M05_{015,035,096,116}`, `TC_M06_080`, `TC_M07_{010,122,146}`, `TC_M14_{012,023}`
   - Explicit 200 response serializers/schemas added across `incidents/api_views.py`, `workorders/views.py`, `dashboards/api_views.py`, `dashboards/serializers.py`, `workspace/api_views.py`, and `workspace/serializers.py` (**165/165** documented `GET` endpoints now have non-empty 200 schemas).

### 3B. Render QA Environment / Test-Data Preconditions — Not Code Defects (52 Cases)

- **20 cases (`technician_max_jobs_exceeded`):** `TC_M06_{036,046,066,101,111,116,117,122}`, `TC_M07_{019,042,051,069,088,098}`, `TC_E2E_{001,004,005,016,017,023}` — shared QA technician account had already reached `max_active_jobs=3`.
- **17 cases (No safe disposable fixture on shared Render DB):** `TC_AUTH_{005,008}`, `TC_M01_{028,114,119}`, `TC_M05_071`, `TC_M06_016`, `TC_M11_{012,028,050,066}`, `TC_M13_{061,072,087,092,097,102}`.
- **13 cases (Empty collections on shared Render DB):** `TC_M07_{011,015,029,033,047,056,065,074}`, `TC_M11_{007,045}`, `TC_M13_{017,077,082}`.
- **1 case (Portal user lacking assets):** `TC_M13_123` — QA portal client had no assigned asset grants.
- **1 case (Playwright cascading dropdown script):** `TC_M01_357` — verified in `src/apps/sites/forms.py` (`SiteForm`) and `src/static/js/app.js` that Country → State → City cascading `<select>` fields work properly in application code; QA Playwright script did not drive the dependent events.

---

## 4. All 64 `SKIPPED` Cases — Breakdown

- **25 cases (`TC_IDRBAC_209`–`233`):** Platform Super Admin uses a separate admin console rather than tenant `/app/*` navigation expectations.
- **30 cases (`TC_IDRBAC_{193..195,363..386}`, `TC_M06_148`, `TC_M08_152`, `TC_M09_302`):** Shared QA client user held custom site-scoped role `'Custom - Raveen Fernando'` instead of the standard Client template.
- **9 intentional / optional spec ambiguities (left unchanged to preserve existing features & tests):**
  1. `TC_AUTH_048` (`POST /auth/logout/`): No stateless access-token revocation/logout endpoint exists (refresh token blacklist only).
  2. `TC_AUTH_049` (`POST /auth/token/`): `django-axes` 5-failure lockout applies to web login; JWT `/auth/token/` enforces `10/min` IP throttle.
  3. `TC_AUTH_070` (`UI /accounts/login/`): Authenticated users visiting `/accounts/login/` redirect to `/app/`.
  4. `TC_M05_178` (`POST /service-requests/`): Intentional `validate_alphabetical_description` rejects digits in titles.
  5. `TC_M06_130` (`POST /work-orders/{id}/transition/`): Empty request body validates `action` (`400`) before action-specific RBAC (`403`).
  6. `TC_M07_116` (`POST /workspace/profile/availability/`): Self-service endpoint open to any active member (`400` on missing `status`).
  7. `TC_M13_098`, `TC_M13_103` (`POST /portal/requests/{id}/reopen[/]`): Serializer body validation (`reason` required → `400`) executes before `404` object lookup.
  8. `TC_M14_030` (`GET /dashboards/{section}/`): Reversed `from`/`to` dates are normalized to a 31-day window ending at `to`.

---

## 5. Local Verification Results

- **Excel Defect Regression Suite (`tests/test_excel_defects_regression.py`):** **10/10 passed**.
- **OpenAPI Schema (`manage.py spectacular --validate`):** **Passed (exit code `0`)** — **165/165** `GET` endpoints have non-empty 200 schemas and **0** unused path parameters.
- **Django Test Suite (`pytest --ignore=tests/qa_playwright -q --tb=line`):** **1,168 passed, 11 failed** (improved from pre-edit baseline **1,144 passed, 14 failed**; includes **11/11** passing negative-path tests in `tests/test_negative_paths_comprehensive.py`).
   - *All 11 failures are pre-existing on `HEAD` and unrelated to the defect fixes:* 4 in `tests/checklists/test_m08_checklists.py`, 4 alphabetical/integer form-validation tests (`test_quantity_rejects_decimals_across_inventory_ui`, `test_portal_request_create_view_submits_with_site`, `test_browser_ui_creation_with_linked_incident`, `test_create_work_order_form_contains_only_creation_fields`), 1 unscoped query check (`test_unscoped_is_only_used_in_trusted_modules`), and 2 UI invitation tests (`test_invite_form_persists_and_audits`, `test_resend_invitation_sends_email` where `InviteForm.password` is required in `HEAD` while those two tests omit `password`).
- **Pending Migrations Check (`manage.py makemigrations --check --dry-run`):** Reports **only** one pre-existing untouched `assets` alteration (`AssetDocument.doc_type`), with zero unmigrated model changes from this branch.

---

## 6. Deployment Checklist for Live Render Verification

1. Deploy branch `fix/api` to `https://fieldops-vpd-yrrh.onrender.com`.
2. Run `python manage.py migrate` to apply:
   - `maintenance/0007_reconcile_legacy_columns.py`
   - `dashboards/0002_sync_schema.py`
   - `workspace/0004_ensure_worknote_table.py`
3. Re-run QA using:
   - A technician account with fewer than 3 active jobs (`max_active_jobs=3`)
   - Clean seeded data / portal asset grants for the client account
   - Standard Client role credentials for client RBAC checks
   - Dependent `<select>` triggers for Country → State → City in Playwright (`/app/sites/`)
