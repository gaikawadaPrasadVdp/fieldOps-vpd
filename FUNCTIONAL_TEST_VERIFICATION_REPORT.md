# FieldOps Nexus — Functional Testing Resolution & Verification Report

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

