# FieldOps Nexus — Negative Path Test Execution Report

- **Branch:** `fix/api` (`c:\f\FieldOps_Nexus_Internal`)
- **Test Database:** PostgreSQL (`test_fieldops` via `TEST_DATABASE_URL`)
- **Test Date:** 2026-11-09
- **Test Suites Executed:**
  - `tests/test_negative_paths_comprehensive.py` (**11/11 passed**; schema-driven sweep across all **294** OpenAPI paths + UI negative security)
  - 18-suite targeted regression & validation run (`tests/test_negative_paths_comprehensive.py`, `tests/test_platform_admin_organizations.py`, `tests/test_sla_business_hours.py`, `tests/test_sla_hold_pause.py`, `tests/test_sla_prd_closure.py`, `tests/test_excel_defects_regression.py`, `tests/test_rbac.py`, `tests/test_db_role_hardening.py`, `tests/test_role_scoping.py`, `tests/test_account_validations.py`, `tests/test_asset_workflow_validations.py`, `tests/test_document_upload_validation.py`, `tests/test_email_and_invite_validations.py`, `tests/test_part_and_portal_form_validations.py`, `tests/test_site_form_validation.py`, `tests/test_workorder_form_alphabetical_validation.py`, `tests/test_workorder_labor_enforcement.py`, `tests/test_portal_m13_remediation_regressions.py`)
  - Full repository suite (`pytest --ignore=tests/qa_playwright -q --tb=line`)

---

## 1. Overall Execution Summary

- **Comprehensive Negative Suite (`tests/test_negative_paths_comprehensive.py`):** **`11 passed in 32.30s`** (`0` failures, `0` xfails, `0` skips)
- **Targeted 18-Suite Regression Run:** **`180 passed in 133.03s`** (`0` failures, `0` xfaiin neagative path all issues resolved or pending anythingls, `0` skips)
- **Full Repository Pytest (`pytest --ignore=tests/qa_playwright`):** **`1,168 passed, 11 failed`** (same 11 pre-existing `HEAD` failures; **0 regressions** introduced)
- **OpenAPI Schema Validation (`manage.py spectacular --validate`):** **Exit code `0`**
- **Excel Negative Polarity Baseline (`2,729` Negative cases in workbook):**
  - Previously `2,614 PASS`, **`51 FAIL`**, **`1 BLOCKED`**, **`63 SKIPPED`**
  - All **`51` negative `FAIL`** cases + **`1` negative `BLOCKED`** case (`TC_M14_016`) are resolved and passing on local `fix/api`
  - **`63` negative `SKIPPED`** cases remain QA role/console setup or intentional spec ambiguities

---

## 2. Schema-Driven Live Negative Sweep (All 294 OpenAPI API Paths)

| Negative Vector | Checks Run | Passed | Issues Remaining | Result Summary |
|---|---:|---:|---:|---|
| **1. Unauthenticated access (`401` + JSON envelope)** | **292** | **292** | **0** | **PASS** — Every protected OpenAPI route rejected anonymous access with JSON `401` (including CSV/PDF/ZIP download endpoints fixed in `DEF-013`). |
| **2. Unsupported HTTP methods (`405` before `403`)** | **584** | **584** | **0** | **PASS** — Every documented path returned `405 Method Not Allowed` for undocumented methods (`PUT`/`PATCH`/`DELETE`/`POST`/`GET`), verifying `DEF-011`. |
| **3. Non-existent valid UUID lookups (`404` JSON, no `500`)** | **251** | **251** | **0** | **PASS** — Random unknown UUIDs returned JSON `404`/`400` cleanly across all parameterized ID endpoints with zero `500`s or HTML `404`s. |
| **4. Malformed non-UUID path ID (`not-a-valid-uuid`)** | **251** | **251** | **0** | **PASS (All Fixed)** — All **8** `ValidationError` (`500`) crashes and **31** `<uuid:...>` HTML `404` responses now return clean JSON `404` (`code="not_found"`). |
| **5. Read-only Auditor & non-admin RBAC boundaries** | **220+** | **220+** | **0** | **PASS** — Zero unauthorized mutations succeeded for Auditor (`POST /api/v1/notifications/read-all/` excluded as intentional self-service); zero `500`s; `6/6` `/api/v1/platform/*` path groups returned `403` to Tenant Owner. |

---

## 3. Targeted Negative Path Scenarios Verified (`PASS`)

1. **Malformed UUID & API JSON Error Envelopes (Newly Fixed & Verified):**
   - All **8** ViewSet malformed-UUID crashes (`GET`/`DELETE /api/v1/escalations/not-a-valid-uuid/`, `GET`/`DELETE /api/v1/sla-escalations/not-a-valid-uuid/`, `GET`/`DELETE /api/v1/platform/organizations/not-a-valid-uuid/`, `POST /api/v1/platform/organizations/not-a-valid-uuid/set_status/`, `POST /api/v1/platform/organizations/not-a-valid-uuid/users/`) now return HTTP `404` JSON (`{"error": {"code": "not_found", ...}}`).
   - `GET /api/v1/escalations/?profile=not-a-valid-uuid` returns HTTP `200` with `results: []` instead of crashing with `ValidationError`.
   - All `<uuid:...>` URL-resolver mismatches (`/api/v1/platform/organizations/{id}/status/`, `/api/v1/workspace/jobs/{id}/*`, `/api/v1/workspace/shifts/{id}/`, `/api/v1/workspace/technicians/{id}/*`, `/api/v1/dashboards/snapshots/{id}/`, `/api/v1/requests|service-requests/{id}/comments/{comment_id}/`) and unknown `/api/*` paths return JSON `404` (`code="not_found"`), while unknown UI routes (`/app/*`) preserve HTML `404` templates.
2. **Cross-Tenant Isolation (API + UI):**
   - Tenant B Owner targeting Tenant A Sites, Assets, Warehouses, Parts, Service Requests (`/service-requests/` & `/requests/`), Work Orders, Maintenance Plans, and Workspace Jobs received `404` (`GET`/`PATCH`) with `beta-utilities` and `403` when spoofing `X-Organization: alpha-industries`.
   - Tenant B Owner opening Tenant A `/app/{sites,assets,work-orders,incidents,maintenance/plans}/<id>/` UI pages received `404`.
3. **Authentication, Rate Limiting & Malformed Payloads:**
   - Invalid credentials, unknown user emails, tampered Bearer JWTs (`401` JSON), invalid refresh tokens (`401` JSON), and suspended memberships (`403`) all rejected cleanly.
   - 5,000-character email boundary (`DEF-005`) and invalid JSON syntax `{bad json` returned JSON `400` (no `500`).
   - JWT `/api/v1/auth/token/` rate limit (`DEF-006`) enforced `429 Too Many Requests` after 10 attempts/min under production `10/min` setting (`config/settings/base.py`).
4. **Domain State Machines & Validation Boundaries:**
   - Inventory negative/zero receipt quantity (`0`, `-5`) returned `400`.
   - Over-reservation (`999`) returned `409`.
   - Work-order part `issue` directly from `REQUESTED` (`DEF-015`) returned `409` (`code="reservation_required"`).
   - Premature `POST /work-orders/{id}/close/`: `403` when lacking `work_order.close`, `400` on empty `{}` payload, `409` on valid payload in invalid state (`IN_PROGRESS`).
   - Duplicate PM schedule returned `409 duplicate_schedule` while non-duplicate schedules succeeded (`DEF-001`).
   - Unknown dashboard section `/api/v1/dashboards/nonexistent_section/` returned `404`/`400`.
5. **UI Security, CSRF & Form Boundaries:**
   - Unauthenticated requests to `/app/` routes redirected `302 -> /accounts/login/`.
   - Read-only Auditor received `403` on write/admin UI pages (`/app/users/invite/`, `/app/roles/new/`, `/app/assets/new/`, `/app/inventory/parts/new/`) and `POST /app/users/<id>/`.
   - `GET /accounts/logout/` returned `405`; missing CSRF token on `POST /app/assets/new/` returned `403`.
   - Asset UI `250`-character name rejected at server (`max_length=200`, `DEF-010`) without silent truncation; Parts UI rejected invalid symbols (`BAD$PART!`) while accepting `FT-UI-*` / `EA` (`DEF-007`).

---

## 4. Root Cause & Fixes Applied for the 8 Identified Negative-Path Defects

### A. Malformed UUID ViewSet Lookups (All 8 Identified Crashes Fixed)

- **Root Cause:** Direct ORM `.filter(pk=pk)` / `get_object_or_404(..., pk=pk)` queries on `UUIDField` primary keys raised unhandled `django.core.exceptions.ValidationError` (`['"not-a-valid-uuid" is not a valid UUID.']`) when given non-UUID strings, producing HTTP `500` in WSGI instead of JSON `404`.
- **Fixes Applied:**
  1. `src/apps/sla/api_views.py` — Added `EscalationViewSet._get_rule(self, request, pk)` (parses `uuid.UUID(str(pk))` and raises `NotFound("Escalation rule not found.")` on `ValueError`/`TypeError`), wired into `retrieve` and `destroy`, and guarded `EscalationViewSet.list` `?profile=` query filtering (`qs.none()` on malformed UUID):
     - Fixes `GET /api/v1/escalations/{id}/`
     - Fixes `DELETE /api/v1/escalations/{id}/`
     - Fixes `GET /api/v1/sla-escalations/{id}/`
     - Fixes `DELETE /api/v1/sla-escalations/{id}/`
  2. `src/apps/tenancy/api_views.py` — Added `PlatformOrganizationViewSet._get_org(self, pk)` (parses `uuid.UUID(str(pk))` and raises `Http404("Organization not found.")` on `ValueError`/`TypeError` before `get_object_or_404(Organization, pk=org_uuid)`), wired into `retrieve`, `destroy`, `set_status`, and `create_user`:
     - Fixes `GET /api/v1/platform/organizations/{id}/`
     - Fixes `DELETE /api/v1/platform/organizations/{id}/`
     - Fixes `POST /api/v1/platform/organizations/{id}/set_status/`
     - Fixes `POST /api/v1/platform/organizations/{id}/users/`

### B. Follow-Up Fix: API Error Handlers Returning HTML Templates on Resolver 404s

- **Discovery:** Once the 8 ViewSet `500` crashes were eliminated, `test_neg_parameterized_routes_malformed_uuid_no_500` surfaced **31** additional `<uuid:...>` parameterized API operations (across `/api/v1/dashboards/snapshots/{id}/`, `/api/v1/platform/organizations/{id}/status/`, `/api/v1/requests|service-requests/{id}/comments/{comment_id}/`, `/api/v1/workspace/jobs/{id}/*`, `/api/v1/workspace/shifts/{id}/`, and `/api/v1/workspace/technicians/{id}/*`) where Django's URL resolver failed before DRF and fell through to `apps.ui.views.not_found`, returning HTML `errors/404.html` instead of JSON.
- **Fix Applied:** Added `_api_error_json` in `src/apps/ui/views.py` and updated `forbidden`, `not_found`, and `server_error` so `/api/*` requests return standard JSON API error envelopes (`{"error": {"code": ..., "message": ..., "details": {}, "request_id": ...}}`), while `/app/*` and web requests continue rendering HTML error templates.
- **Verification:** `test_neg_parameterized_routes_malformed_uuid_no_500` and `test_neg_malformed_uuid_escalations_platform_and_api_404_envelope` now both **PASS** (`251 / 251` checks, `0` crashes, `0` non-JSON `404`s).
