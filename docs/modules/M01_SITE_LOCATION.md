# M01 Site & Location Master — Technical Specification & Module Guide

Part of the ONE integrated FieldOps Nexus ERP. Read `docs/PROJECT_SOURCE_OF_TRUTH.md` and `docs/FIELDOPS_NEXUS_MASTER_BUSINESS_WORKFLOW.md` first.

- **Module Code:** M01
- **Django Application:** `apps.sites`
- **HPE PRD Scope Reference:** Section 7.2 (REQ-ORG-01: Multi-tenant site master management, buildings, zones, service areas, operating calendars, shifts, contact hierarchy)
- **Status:** 🟢 **FINALIZED, VERIFIED & PRODUCTION SIGNED-OFF**
- **Authoritative Ownership:** `Site`, `Zone`, `Shift`, `OperatingCalendar`, `CalendarHoliday`, `SiteContact`.

---

## 1. Purpose & Business Architecture

The Site & Location Master establishes the geographic and spatial hierarchy of physical operations across an enterprise organization. Every physical asset, warehouse inventory balance, scheduled maintenance plan, dispatched work order, and service request operates within the context of an authoritative Site and optional Zone/Building sub-location.

### Core Functional Questions Answered
1. Where does an organization operate physically?
2. Which buildings, floors, rooms, or production lines exist within a facility?
3. What are the operating hours, work shifts, and statutory holidays governing SLA clocks?
4. Who are the primary emergency, technical, and operational contacts responsible for a location?

---

## 2. Spatial Hierarchy & Data Model

```
Organization (Tenant Boundary)
  └── Site (Physical Facility / Campus / Plant)
        ├── OperatingCalendar (Weekly Schedule & Business Hours)
        │     └── CalendarHoliday (Statutory & Site-Specific Non-Working Days)
        ├── Shift (Operational Work Shifts, e.g., Morning, Swing, Graveyard)
        ├── SiteContact (Multi-Tier Contact Hierarchy: Emergency, Operations, Security)
        └── Zone (Multi-Level Location Hierarchy: Building → Floor → Room → Line)
```

### 2.1 Entity Model Specifications (`src/apps/sites/models.py`)

1. **`Site`:**
   - Multi-tenant facility master uniquely identified by `(organization, code)`.
   - Fields: `code` (e.g. `PLANT-1`, `BLR-DC`), `name`, `description`, `address`, `city`, `state_region`, `postal_code`, `country`, `timezone`, `status` (`ACTIVE`, `INACTIVE`), `status_reason`, `contact_name`, `contact_email`, `contact_phone`.
   - Invariants: Cannot be deactivated if active physical assets, unreserved warehouse inventory, or active work orders remain attached. Hard deletions are forbidden (`models.ProtectedError` and soft status toggle).

2. **`Zone`:**
   - Spatial sub-location within a site supporting recursive self-referencing tree structures (`parent_id`).
   - Fields: `site`, `name`, `code`, `kind` (`BUILDING`, `FLOOR`, `ROOM`, `AREA`, `PRODUCTION_LINE`, `STORAGE`), `parent`, `is_active`.
   - Invariants: Cyclic parent-child relationships are strictly prevented by transactional loop detection.

3. **`OperatingCalendar` & `CalendarHoliday`:**
   - Authoritative schedule governing SLA elapsed-time calculations.
   - Defines standard operating windows per day of week (Monday through Sunday) with start and end times.
   - Holidays pause SLA response/resolution clocks when `calendar_aware=True`.

4. **`Shift`:**
   - Operational work shifts defining work windows (`start_time`, `end_time`, `days_of_week`) per site.
   - Linked to technician dispatch eligibility and capacity utilization metrics.

5. **`SiteContact`:**
   - Structured emergency and operational directory with escalation levels (`escalation_order` 1 through 5).

---

## 3. Boundary Rules & Downstream Integration

- **Downstream Consumers:**
  - **M02 Asset Registry:** Assets require a valid, active `Site` and optional `Zone`.
  - **M04 Preventive Maintenance:** Recurring schedules evaluate site operating calendars and timezone offsets.
  - **M05 Incident Management & M06 Work Orders:** Tickets inherit site context, determining technician routing and SLA profiles.
  - **M07 Technician Workspace:** Technicians view site emergency contacts, dispatch addresses, and GPS route actions.
  - **M09 Inventory & Warehouses:** Warehouses map to a parent Site.
  - **M11 SLA Engine:** Wall-clock timers evaluate Site Operating Calendars and Holidays to pause SLA timers outside business hours.

- **Hard Boundary Rules:**
  - Sites never own assets, incidents, or work orders directly.
  - Cross-tenant site assignment is strictly blocked at both ORM and database foreign-key tenant scopes.
  - Deactivation of a site is refused (`ValidationFailed`) if active child dependencies exist.

---

## 4. Security & RBAC Enforcement

All operations require an authenticated user with an active membership in the target organization. Permissions are enforced fail-closed by `TenantPermissionMixin` and `require_permission`:

| Permission Code | Description | Permitted Roles |
| :--- | :--- | :--- |
| `site.view` | View sites, zones, shifts, calendars, contacts | All internal staff roles, Client (read-only self-site) |
| `site.create` | Create new site master records and zones | Organization Owner, Operations Manager |
| `site.update` | Edit site details, address, calendars, contacts | Organization Owner, Operations Manager |
| `site.deactivate` | Toggle site active/inactive state | Organization Owner only |

---

## 5. User Interface & Workflow Views

- **`/app/sites/` (`SiteListView`):** Search, status filtering (`ACTIVE`/`INACTIVE`), zone counts, asset counts, and responsive cards.
- **`/app/sites/new/` (`SiteCreateView`):** Site creation wizard with country/state dependent selectors and timezone autocompletion.
- **`/app/sites/<pk>/` (`SiteDetailView`):** Multi-tab facility dossier:
  - *Overview Tab:* Facility metadata, address, contact persons, status badges.
  - *Zones Tab:* Interactive tree visualizer and sub-location registry.
  - *Calendars Tab:* Weekly operating schedule and holiday exception calendar.
  - *Shifts Tab:* Workday shift assignments and capacity hours.
  - *Contacts Tab:* Emergency escalation hierarchy.
- **`/app/sites/<pk>/edit/` (`SiteEditView`):** In-place metadata editing.
- **`/app/sites/<pk>/deactivate/`:** Confirmation modal with dependency pre-flight validation.

---

## 6. Verification & Quality Assurance Traceability

- **Automated Pytest Coverage:** `tests/test_sites.py`, `tests/test_m01_site_location.py`, `tests/unit_spec/test_part1_org_ast_mtr_pm.py` (`TC-ORG-003`).
- **REST API Test Specifications:** See `docs/testing/M01_API_TEST_REPORT.md` (12/12 Automated Endpoint Tests Passed).
- **Formal Sign-Off Certification:** See `docs/SITE_ASSET_QR_FINAL_ACCEPTANCE_SIGNOFF_REPORT.md`.
