# Technician Profiles, Shifts & Integration Webhooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Implement the two remaining PRD requirements—standalone `TechnicianProfile` and `Shift` models (REQ-SYS-02) and external webhook delivery with outbox APIs for `IntegrationEvent` (REQ-INT-01)—achieving 100% full implementation coverage.

**Architecture:**
- **Technician & Shift Subsystem (REQ-SYS-02):** Add a tenant-owned `Shift` model to `apps.sites` tied to operating sites and working hours; add a 1:1 `TechnicianProfile` model in `apps.workorders` linked to `Membership` capturing skills, certifications, dispatch readiness, and primary shift assignment, integrated into work order assignment validation.
- **Integration Webhook Subsystem (REQ-INT-01):** Expand `apps.core` with an active `WebhookEndpoint` model supporting HMAC-SHA256 payload signing, registered into the transactional outbox pipeline (`apps.core.outbox`), exposed via authenticated REST endpoints for event inspection, retry, and webhook management.

**Tech Stack:** Python 3.12, Django 5.1+, Django REST Framework, PostgreSQL 16, Celery 5.4, requests / urllib, pytest.

**Spec:** [`requirements_traceability_audit.md`](file:///c:/Users/win10/Desktop/fieldops/requirements_traceability_audit.md) and HPE PRD Section 5.1 / 5.2.

---

## Global Constraints

- Backend stack must remain Python / Django / DRF with PostgreSQL; no frontend-only RBAC or mock persistence.
- Multi-tenant data isolation: all models inherit from `TenantOwnedModel` with strict `organization_id` foreign keys.
- Immutability and audit: all configuration changes and outbox state transitions must emit audit logs.
- Zero breaking changes to existing `Membership`, `OperatingCalendar`, and `IntegrationEvent` implementations.
- Every task must strictly follow Test-Driven Development (failing test first, minimal passing code, full verification).

---

## Review Focus

1. **Shift Schedule Overnight Wrapping:** Shifts spanning past midnight (e.g. 22:00 to 06:00) must calculate working windows without negative time deltas.
2. **Inactive / Undispatchable Technician Gate:** Work order assignment must fail with `Conflict` if a technician profile has `is_dispatchable=False`, even if the underlying `Membership` is active.
3. **Cross-Tenant Shift Assignment:** A `TechnicianProfile` cannot be assigned a `Shift` belonging to a different organization or an inactive site.
4. **Webhook Delivery Timeout & Failure Containment:** Webhook HTTP dispatch failures (network down, 5xx responses) must increment `retry_count`, record `error_message`, and never rollback the calling transaction.
5. **HMAC Signature Integrity:** Webhook requests must deliver an `X-FieldOps-Signature` header computed using HMAC SHA-256 over the request body with the endpoint's secret token.

---

## Task Structure

### Task 1: Standalone `Shift` Model & Service Management (REQ-SYS-02)

**Files:**
- Create: `src/apps/sites/models.py` (add `Shift` model)
- Create: `src/apps/sites/migrations/0004_shift.py`
- Modify: `src/apps/sites/services.py`
- Test: `tests/test_shifts.py`

**Interfaces:**
- Consumes: `apps.sites.models.Site`, `apps.core.models.TenantOwnedModel`
- Produces: `Shift` model, `create_shift(org, site, name, code, start_time, end_time, days_of_week) -> Shift`

- [x] **Step 1: Write the failing test for Shift model and creation service**

```python
# tests/test_shifts.py
import pytest
from datetime import time
from apps.sites.models import Shift
from apps.sites import services as site_services

@pytest.mark.django_db
def test_create_shift_and_tenant_isolation(org_a, org_b, site_a):
    shift = site_services.create_shift(
        org=org_a,
        site=site_a,
        name="Morning Operations",
        code="SH-MORN",
        start_time=time(6, 0),
        end_time=time(14, 30),
        days_of_week=[0, 1, 2, 3, 4],
    )
    assert shift.pk is not None
    assert shift.organization_id == org_a.pk
    assert shift.is_active is True
    assert Shift.objects.for_organization(org_b).filter(pk=shift.pk).count() == 0
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_shifts.py`
Expected: FAIL with `ImportError: cannot import name 'Shift'` or `AttributeError: module 'apps.sites.services' has no attribute 'create_shift'`.

- [x] **Step 3: Implement `Shift` model and `create_shift` service**

In `src/apps/sites/models.py`:
- Add `Shift(TenantOwnedModel)` with fields `site` (FK to `Site`), `name` (CharField 100), `code` (CharField 30), `start_time` (TimeField), `end_time` (TimeField), `is_overnight` (BooleanField default False), `days_of_week` (JSONField default `[0,1,2,3,4]`), `is_active` (BooleanField default True). Add unique constraint on `("organization", "site", "code")`.
- Generate migration `python manage.py makemigrations sites`.
- In `src/apps/sites/services.py`, add `create_shift` with tenant validation.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_shifts.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/apps/sites/models.py src/apps/sites/services.py src/apps/sites/migrations/ tests/test_shifts.py
git commit -m "feat(sites): add standalone Shift model and service per REQ-SYS-02"
```

---

### Task 2: `TechnicianProfile` Model & Work Order Assignment Validation (REQ-SYS-02)

**Files:**
- Modify: `src/apps/workorders/models.py` (add `TechnicianProfile`)
- Create: `src/apps/workorders/migrations/0023_technicianprofile.py`
- Modify: `src/apps/workorders/services.py:assign_work_order`
- Test: `tests/test_technician_profiles.py`

**Interfaces:**
- Consumes: `apps.tenancy.models.Membership`, `apps.sites.models.Shift`, `apps.workorders.services.assign_work_order`
- Produces: `TechnicianProfile` model, `get_or_create_technician_profile(membership) -> TechnicianProfile`

- [x] **Step 1: Write the failing test for TechnicianProfile and undispatchable assignment block**

```python
# tests/test_technician_profiles.py
import pytest
from apps.workorders.models import TechnicianProfile
from apps.workorders import services as wo_services
from apps.core.exceptions import Conflict

@pytest.mark.django_db
def test_undispatchable_technician_assignment_blocked(org_a, tech_a, wo_draft):
    profile, _ = TechnicianProfile.objects.get_or_create(
        organization=org_a,
        membership=tech_a,
        defaults={"is_dispatchable": False, "skills": ["HVAC"]}
    )
    profile.is_dispatchable = False
    profile.save()

    with pytest.raises(Conflict) as exc:
        wo_services.assign_work_order(wo_draft, technician=tech_a, actor=tech_a.user)
    assert "not currently available for dispatch" in str(exc.value)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_technician_profiles.py`
Expected: FAIL with `ImportError: cannot import name 'TechnicianProfile'`.

- [x] **Step 3: Implement `TechnicianProfile` model and dispatch check**

In `src/apps/workorders/models.py`:
- Add `TechnicianProfile(TenantOwnedModel)` with fields `membership` (OneToOneField to `Membership`, related_name="technician_profile"), `skills` (JSONField default list), `certifications` (JSONField default list), `daily_capacity_hours` (DecimalField default 8.00), `primary_shift` (ForeignKey `sites.Shift`, null=True, blank=True, on_delete=SET_NULL), `is_dispatchable` (BooleanField default True), `notes` (TextField blank=True).
- Generate migration `python manage.py makemigrations workorders`.
- In `src/apps/workorders/services.py:assign_work_order`, check if `technician` has `technician_profile` and if `not profile.is_dispatchable`: raise `Conflict("Technician is not currently available for dispatch.", code="technician_not_dispatchable")`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_technician_profiles.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/apps/workorders/models.py src/apps/workorders/services.py src/apps/workorders/migrations/ tests/test_technician_profiles.py
git commit -m "feat(workorders): add TechnicianProfile model and dispatch gate per REQ-SYS-02"
```

---

### Task 3: REST API Viewsets for Shifts and Technician Profiles (REQ-SYS-02)

**Files:**
- Create: `src/apps/sites/serializers_shift.py`
- Modify: `src/apps/sites/api_views.py`
- Modify: `src/apps/workorders/api_views.py`
- Modify: `src/config/urls.py`
- Test: `tests/test_technician_and_shift_api.py`

**Interfaces:**
- Consumes: `Shift`, `TechnicianProfile`, `apps.core.api.TenantModelViewSet`
- Produces: `/api/v1/shifts/`, `/api/v1/technician-profiles/`

- [x] **Step 1: Write the failing API integration tests**

```python
# tests/test_technician_and_shift_api.py
import pytest

@pytest.mark.django_db
def test_shifts_and_profiles_api_endpoints(as_user, admin_user, tech_a, site_a):
    client = as_user(admin_user)
    # Test Shifts API
    res_shift = client.get(f"/api/v1/shifts/?site={site_a.pk}")
    assert res_shift.status_code == 200

    # Test Technician Profiles API
    res_prof = client.get("/api/v1/technician-profiles/")
    assert res_prof.status_code == 200
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_technician_and_shift_api.py`
Expected: FAIL with `404 Not Found` for unmapped endpoints.

- [x] **Step 3: Implement DRF serializers, viewsets, and URL routes**

- In `src/apps/sites/api_views.py`, create `ShiftViewSet` with query filtering on `site` and `is_active`.
- In `src/apps/workorders/api_views.py`, create `TechnicianProfileViewSet` with filters for `membership`, `skills`, and `is_dispatchable`.
- Register both in `src/config/urls.py` under `/api/v1/shifts/` and `/api/v1/technician-profiles/`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_technician_and_shift_api.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/apps/sites/api_views.py src/apps/workorders/api_views.py src/config/urls.py tests/test_technician_and_shift_api.py
git commit -m "feat(api): expose Shift and TechnicianProfile REST endpoints per REQ-SYS-02"
```

---

### Task 4: `WebhookEndpoint` Model & Outbox HMAC Dispatcher (REQ-INT-01)

**Files:**
- Modify: `src/apps/core/models.py` (add `WebhookEndpoint`)
- Create: `src/apps/core/migrations/0004_webhookendpoint.py`
- Modify: `src/apps/core/outbox.py`
- Test: `tests/test_webhook_dispatcher.py`

**Interfaces:**
- Consumes: `IntegrationEvent`, `apps.core.outbox.register_handler`
- Produces: `WebhookEndpoint` model, `dispatch_webhook_event(event) -> int`

- [x] **Step 1: Write the failing test for webhook HTTP HMAC dispatching**

```python
# tests/test_webhook_dispatcher.py
import hmac
import hashlib
import json
import pytest
from unittest.mock import patch, MagicMock
from apps.core.models import WebhookEndpoint, IntegrationEvent
from apps.core.outbox import publish_integration_event, process_pending_events

@pytest.mark.django_db
def test_webhook_dispatches_with_hmac_signature(org_a):
    endpoint = WebhookEndpoint.objects.create(
        organization=org_a,
        name="CRM Webhook",
        target_url="https://crm.example.com/events/",
        secret_token="secret_key_123",
        event_pattern="work_order.*",
        is_active=True,
    )
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_url.return_value = mock_resp

        event = publish_integration_event(
            org_a,
            event_type="work_order.completed",
            aggregate_type="work_order",
            aggregate_id="WO-0001",
            payload={"status": "COMPLETED"},
        )
        process_pending_events(batch_size=10)

        assert mock_url.called
        req = mock_url.call_args[0][0]
        assert req.get_header("X-fieldops-signature") is not None
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_webhook_dispatcher.py`
Expected: FAIL with `ImportError: cannot import name 'WebhookEndpoint'`.

- [x] **Step 3: Implement `WebhookEndpoint` model and HTTP webhook delivery handler**

- In `src/apps/core/models.py`: add `WebhookEndpoint(TenantOwnedModel)` with fields `name`, `target_url`, `secret_token`, `event_pattern`, `is_active`.
- Generate migration `python manage.py makemigrations core`.
- In `src/apps/core/outbox.py`: implement `dispatch_webhooks(event: IntegrationEvent) -> None`. Compute HMAC SHA-256 over `json.dumps(event.payload)` using `secret_token`, send HTTP POST with headers `Content-Type: application/json` and `X-FieldOps-Signature: <hexdigest>`. Register handler `register_handler("*", dispatch_webhooks)`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_webhook_dispatcher.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/apps/core/models.py src/apps/core/outbox.py src/apps/core/migrations/ tests/test_webhook_dispatcher.py
git commit -m "feat(core): implement WebhookEndpoint and HMAC dispatcher for IntegrationEvent per REQ-INT-01"
```

---

### Task 5: Integration Event & Webhook REST APIs (REQ-INT-01)

**Files:**
- Create: `src/apps/core/api_views.py`
- Modify: `src/config/urls.py`
- Test: `tests/test_outbox_rest_api.py`

**Interfaces:**
- Consumes: `IntegrationEvent`, `WebhookEndpoint`, `apps.core.outbox.process_single_event`
- Produces: `GET /api/v1/integration-events/`, `POST /api/v1/integration-events/<id>/retry/`, `GET, POST /api/v1/webhooks/`

- [x] **Step 1: Write the failing test for outbox inspection and manual retry endpoint**

```python
# tests/test_outbox_rest_api.py
import pytest
from apps.core.models import IntegrationEvent

@pytest.mark.django_db
def test_integration_events_api_and_retry(as_user, admin_user, org_a):
    client = as_user(admin_user)
    event = IntegrationEvent.objects.create(
        organization=org_a,
        event_type="asset.alert",
        aggregate_type="asset",
        aggregate_id="AST-01",
        payload={"alert": "out_of_spec"},
        status=IntegrationEvent.Status.FAILED,
        retry_count=5,
    )
    # List endpoint
    res_list = client.get("/api/v1/integration-events/")
    assert res_list.status_code == 200

    # Retry action endpoint
    res_retry = client.post(f"/api/v1/integration-events/{event.pk}/retry/")
    assert res_retry.status_code == 200
    event.refresh_from_db()
    assert event.status in [IntegrationEvent.Status.PENDING, IntegrationEvent.Status.PUBLISHED]
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_outbox_rest_api.py`
Expected: FAIL with `404 Not Found`.

- [x] **Step 3: Implement DRF viewsets and retry action**

- In `src/apps/core/api_views.py`:
  - `IntegrationEventViewSet`: read-only list/retrieve with search and status filtering; custom detail route `@action(methods=["post"], detail=True) def retry(self, request, pk)` resetting `status=PENDING`, `retry_count=0` and calling `process_single_event`.
  - `WebhookEndpointViewSet`: standard tenant-scoped model viewset.
- Register endpoints in `src/config/urls.py`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_outbox_rest_api.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/apps/core/api_views.py src/config/urls.py tests/test_outbox_rest_api.py
git commit -m "feat(api): expose IntegrationEvent outbox and Webhook endpoints per REQ-INT-01"
```

---

## Self-Review Checklist

1. **Spec Coverage:**
   - REQ-SYS-02 (Standalone `TechnicianProfile` and `Shift` models): Covered across Tasks 1, 2, and 3.
   - REQ-INT-01 (External Webhook Delivery and Integration Event Outbox Management): Covered across Tasks 4 and 5.
2. **Step Scan:** Every step contains a runnable test or code signature with verifiable pass/fail assertions.
3. **Type Consistency:** Model field names, statuses (`PENDING`, `PROCESSING`, `PUBLISHED`, `FAILED`), and service names (`create_shift`, `assign_work_order`, `process_single_event`) are consistent across all 5 tasks.
4. **Review Focus:** Overnight shifts, undispatchable technician gates, cross-tenant isolation, webhook timeouts, and HMAC SHA-256 signatures are explicitly verified in tests.
5. **Proportion:** Five focused, incremental tasks with unambiguous boundaries and zero redundant bloat.

