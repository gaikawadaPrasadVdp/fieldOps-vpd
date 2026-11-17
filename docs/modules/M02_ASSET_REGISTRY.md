# M02 Asset Registry — Technical Specification & Module Guide

Part of the ONE integrated FieldOps Nexus ERP. Read `docs/PROJECT_SOURCE_OF_TRUTH.md` and `docs/FIELDOPS_NEXUS_MASTER_BUSINESS_WORKFLOW.md` first.

- **Module Code:** M02
- **Django Application:** `apps.assets`
- **HPE PRD Scope Reference:** Section 7.2 (REQ-AST-01: Asset registry tracking make, model, serial number, purchase/commission dates, criticality, status history, document vaults, and category attributes; REQ-AST-03: Equipment meters)
- **Status:** 🟢 **FINALIZED, VERIFIED & PRODUCTION SIGNED-OFF**
- **Authoritative Ownership:** `Asset`, `AssetCategory`, `AssetDocument`, `AssetMeter`, `AssetMeterReading`, `AssetStatusHistory`.

---

## 1. Purpose & Core Responsibilities

The Asset Registry serves as the authoritative single source of truth for all physical equipment, machinery, facilities, vehicles, and instrumentation managed across an enterprise organization.

It governs asset identification, category classification with dynamic JSON-schema attributes, lifecycle state transitions, usage meter accumulation, document vaults, and immutable audit trails.

---

## 2. Core Entities & Database Architecture (`src/apps/assets/models.py`)

### 2.1 Entity Model Specifications

1. **`Asset`:**
   - Primary physical master record scoped strictly to `organization` and `site`.
   - Fields: `asset_tag` (unique business code, e.g. `AST-0001`), `name`, `description`, `category` (FK `AssetCategory`), `manufacturer`, `model`, `serial_number`, `purchase_date`, `commission_date`, `site` (FK `Site`), `zone` (FK `Zone`), `owner` (FK `User`), `warranty_ref`, `criticality` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), `status`, `attributes` (JSONField for category-specific dynamic fields).
   - Invariants:
     - `asset_tag` is unique per organization (`unique_together = ("organization", "asset_tag")`).
     - `site` is mandatory; cross-tenant site references are rejected at the ORM layer.
     - `commission_date >= purchase_date` enforced by clean validation.

2. **`AssetCategory`:**
   - Enterprise taxonomy grouping assets with custom field schemas.
   - Fields: `name`, `description`, `is_active`, `attribute_definitions` (JSONField array defining custom schema rules: `label`, `type` [`text`, `number`, `date`, `choice`], `required`, `choices`).

3. **`AssetStatusHistory`:**
   - Append-only chronological audit log tracking every lifecycle transition.
   - Fields: `asset`, `from_status`, `to_status`, `reason`, `changed_by` (FK `User`), `changed_at`.
   - Protected against UPDATE or DELETE statements.

4. **`AssetDocument`:**
   - Digital document vault storing equipment manuals, schematics, safety certifications, and warranty proofs.
   - Supports file verification, MIME-type validation, size limits (up to 25 MB), and soft deletion with audit logging.

5. **`AssetMeter` & `AssetMeterReading`:**
   - Tracks cumulative equipment usage: running hours, operational cycles, production output, or kilometers.
   - Enforces strictly non-decreasing monotonic readings (except when flagged with valid dial rollover math).
   - Serves as the real-time trigger for M04 usage-based Preventive Maintenance work orders.

---

## 3. Finite State Machine & Lifecycle Transitions

Assets follow a strictly controlled state machine. Direct modification of `asset.status` via ordinary edit forms is forbidden; transitions must execute through `apps.assets.services.transition_asset_status`.

```
                    ┌────────────────────────┐
                    │        DRAFT           │
                    └───────────┬────────────┘
                                │ commission()
                                v
                    ┌────────────────────────┐
        ┌──────────>│        ACTIVE          │<──────────┐
        │           └───────┬────────┬───────┘           │
        │                   │        │                   │
        │        wo_start() │        │ flag_defect()     │
        │                   v        v                   │
        │      ┌─────────────────┐ ┌────────────────┐    │
        │      │UNDER_MAINTENANCE│ │ OUT_OF_SERVICE │    │
        │      └────────┬────────┘ └────────┬───────┘    │
        │               │                   │            │
        └───────────────┴─────────┬─────────┴────────────┘
                                  │
                                  │ decommission() / retire()
                                  v
                    ┌────────────────────────┐
                    │   RETIRED / DISPOSED   │ (Terminal States)
                    └────────────────────────┘
```

### 3.1 Architectural Decision D-058 (Bi-Directional Work Order Synchronization)
- When a Work Order on an asset transitions to `IN_PROGRESS`, the asset status automatically transitions to `UNDER_MAINTENANCE` (preserving audit history).
- When the Work Order reaches `COMPLETED` or `CLOSED`, the asset automatically returns to `ACTIVE`.
- Invariant: Automatic work order synchronization never overwrites an asset explicitly placed in `OUT_OF_SERVICE`, `RETIRED`, or `DISPOSED`.

---

## 4. Security & RBAC Enforcement

| Permission Code | Description | Role Assignments |
| :--- | :--- | :--- |
| `asset.view` | View asset details, documents, meter readings, and status history | All internal staff roles, Client (scoped) |
| `asset.create` | Register new assets and upload initial documentation | Organization Owner, Asset Manager |
| `asset.update` | Edit asset metadata, attach manuals, and log meter readings | Organization Owner, Asset Manager, Supervisor |
| `asset.transition`| Execute controlled lifecycle status transitions | Organization Owner, Asset Manager |
| `asset.delete` | Soft decommission / retire an asset | Organization Owner only |

---

## 5. User Interface & Workflow Views

- **`/app/assets/` (`AssetListView`):** Search, status filtering, category facets, site scoping, and CSV export.
- **`/app/assets/new/` (`AssetCreateView`):** Registration wizard with category dynamic attribute rendering.
- **`/app/assets/<pk>/` (`AssetDetailView`):**
  - *Overview Tab:* General specifications, dates, site/zone location, active work order alert banners.
  - *Documents Tab:* Uploaded manuals, warranties, and technical schematics.
  - *Meters Tab:* Cumulative usage gauges, historical reading graphs, and manual reading log modal.
  - *History Tab:* Full timeline of lifecycle state transitions with actor and reason notes.
  - *Hierarchy Tab:* Embedded component tree (M03 integration).
  - *Labels Tab:* Physical QR & Barcode generation, SVG/PNG preview, and label printing (M12 integration).

---

## 6. Verification & Quality Assurance Traceability

- **Automated Pytest Coverage:** `tests/test_assets.py`, `tests/unit_spec/test_part1_org_ast_mtr_pm.py` (`TC-AST-001` through `TC-AST-006`, `TC-MTR-001` through `TC-MTR-004`).
- **REST API Test Specifications:** See `docs/testing/M02_API_TEST_REPORT.md` (15/15 Automated Endpoint Tests Passed).
- **Formal Sign-Off Certification:** See `docs/SITE_ASSET_QR_FINAL_ACCEPTANCE_SIGNOFF_REPORT.md`.
