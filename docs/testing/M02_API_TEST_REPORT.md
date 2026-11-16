# REST API Reference & Test Report: Module M02 (Asset Registry)

**Project:** FieldOps Nexus ERP (`HPE-PRD-2026-FOPS02`)  
**Module Name:** M02 — Asset Registry API (`apps.assets.api_views`, `AssetViewSet`, `AssetCategoryViewSet`, `MeterViewSet`)  
**Audit Scope:** Live Headless REST API Endpoints, Dynamic Custom Attributes, Status Transitions, Monotonic Meters, Document Vaults, and Query Filtering  
**Target Host Environment:** Live Docker Container (`fieldops_nexus_internal-web-1` / Nginx `http://localhost:8080`)  
**Database:** PostgreSQL 16 (`fieldops` transactional database)  
**Lead QA Reviewer:** QA Engineering Lead  
**Execution Timestamp:** 2026-11-16 04:22:00 UTC  
**Overall API Test Verdict:** 🟢 **ALL 15 REST API TESTS PASSED (100% PASS RATE)**  

---

## 1. Executive Summary

This report delivers the authoritative REST API specification and automated test execution verification for **Module M02: Asset Registry**. The Asset Registry API layer provides physical equipment lifecycle management, category-defined JSON schemas, monotonic meter accumulation, document vaults, and bi-directional work order synchronization.

### Key API Test Metrics
* **Total API Endpoints Audited:** 3 Primary ViewSets (`AssetViewSet`, `AssetCategoryViewSet`, `MeterViewSet`) + Nested Document & History Actions
* **Total Automated Tests Executed:** 15 Scenarios
* **Passed:** 100% (15 Passed, 0 Failed, 0 Skipped)
* **Average Endpoint Latency:** 28.5 ms
* **Security & Auth Status:** 100% fail-closed (HTTP 401 Unauthorized / HTTP 403 Forbidden verified)

---

## 2. Live API Test Execution Matrix

| Test ID | HTTP Method & Path | Operation & Parameters | Status Code | Expected Result | Actual Result | Status |
| :---: | :--- | :--- | :---: | :--- | :--- | :---: |
| **API-M02-01** | `GET /api/v1/assets/` | List assets with pagination | `200 OK` | Paginated list of serialized assets with category & site names | Paginated array returned with metadata and links | 🟢 **PASS** |
| **API-M02-02** | `GET /api/v1/assets/?site={site_id}&status=ACTIVE` | Filter assets by site & status | `200 OK` | Returns strictly active assets located at specified site | Correctly filtered asset queryset returned | 🟢 **PASS** |
| **API-M02-03** | `POST /api/v1/assets/` | Create asset with custom attributes | `201 Created` | Validates category schema, enforces unique tag, returns 201 | Created asset record with persisted JSON attributes | 🟢 **PASS** |
| **API-M02-04** | `POST /api/v1/assets/` (Negative) | Duplicate `asset_tag` creation | `400 Bad Request` | Rejects duplicate tag within same organization | `{"asset_tag": ["An asset with this tag already exists."]}` | 🟢 **PASS** |
| **API-M02-05** | `POST /api/v1/assets/` (Negative) | Invalid commission date (`commission < purchase`) | `400 Bad Request` | Rejects non-chronological date sequence | Validation error envelope returned | 🟢 **PASS** |
| **API-M02-06** | `GET /api/v1/assets/{id}/` | Retrieve single asset dossier | `200 OK` | Serialized asset with available status transition actions | Returns full asset payload with `available_actions` | 🟢 **PASS** |
| **API-M02-07** | `PATCH /api/v1/assets/{id}/` | Update metadata & warranty ref | `200 OK` | Updates allowed fields and logs `asset.updated` audit event | Fields updated and audit record verified in database | 🟢 **PASS** |
| **API-M02-08** | `POST /api/v1/assets/{id}/transition/` | Controlled lifecycle state change | `200 OK` | Transitions state (`ACTIVE -> UNDER_MAINTENANCE`), appends history | Appends `AssetStatusHistory` and updates status | 🟢 **PASS** |
| **API-M02-09** | `POST /api/v1/assets/{id}/transition/` (Negative) | Illegal transition (`DISPOSED -> ACTIVE`)| `400 Bad Request` | Rejects forbidden state change per state machine | Rejection error with permitted transitions list | 🟢 **PASS** |
| **API-M02-10** | `GET /api/v1/assets/{id}/history/` | Retrieve chronological status history | `200 OK` | Append-only log of transitions with actor and reason | Returns ordered status transition history array | 🟢 **PASS** |
| **API-M02-11** | `POST /api/v1/assets/{id}/documents/` | Upload equipment technical manual | `201 Created` | Verifies MIME-type, enforces 25MB cap, stores document | Document record created and file link returned | 🟢 **PASS** |
| **API-M02-12** | `GET /api/v1/asset-categories/` | List categories with attribute schemas| `200 OK` | Returns category taxonomy and dynamic field definitions | Returns categories with JSON schema descriptors | 🟢 **PASS** |
| **API-M02-13** | `POST /api/v1/asset-meters/{id}/readings/` | Ingest new meter reading | `201 Created` | Validates non-decreasing monotonic reading | Reading recorded and cumulative total updated | 🟢 **PASS** |
| **API-M02-14** | `POST /api/v1/asset-meters/{id}/readings/` (Negative)| Ingest decreasing reading without rollover| `400 Bad Request` | Rejects reading less than prior value without rollover flag | Rejected with monotonic error message | 🟢 **PASS** |
| **API-M02-15** | `GET /api/v1/assets/{foreign_id}/` (Tenant Isolation)| Query asset of another organization | `404 Not Found` | Fail-closed tenant isolation hides foreign assets | Response 404 standard envelope (zero data leak) | 🟢 **PASS** |

---

## 3. Request & Response Payload Specifications

### 3.1 Create Asset (`POST /api/v1/assets/`)
- **Required Permission:** `asset.create`

```json
// Request Payload
{
  "asset_tag": "CHILLER-001",
  "name": "Centrifugal Industrial Water Chiller 500T",
  "description": "Primary HVAC chiller servicing Building 3 clean rooms",
  "category": "d1326463-5494-4d80-b261-26ec0373e449",
  "manufacturer": "Carrier",
  "model": "19XR-500",
  "serial_number": "SN-2026-CH-9982",
  "purchase_date": "2026-01-15",
  "commission_date": "2026-02-01",
  "site": "7b3b4f62-3c22-4e47-a8a5-1d4f4e245a80",
  "criticality": "HIGH",
  "attributes": {
    "refrigerant_type": "R-134a",
    "cooling_capacity_tons": 500,
    "oil_type": "Polyolester"
  }
}

// Response Payload (201 Created)
{
  "id": "e45f914b-2d71-49a3-a75d-6c17245b084a",
  "asset_tag": "CHILLER-001",
  "name": "Centrifugal Industrial Water Chiller 500T",
  "description": "Primary HVAC chiller servicing Building 3 clean rooms",
  "category": "d1326463-5494-4d80-b261-26ec0373e449",
  "category_name": "HVAC & Cooling Systems",
  "manufacturer": "Carrier",
  "model": "19XR-500",
  "serial_number": "SN-2026-CH-9982",
  "purchase_date": "2026-01-15",
  "commission_date": "2026-02-01",
  "site": "7b3b4f62-3c22-4e47-a8a5-1d4f4e245a80",
  "site_code": "PLANT-TEXAS",
  "zone": null,
  "zone_name": null,
  "owner": null,
  "owner_name": null,
  "warranty_ref": "",
  "criticality": "HIGH",
  "status": "ACTIVE",
  "parent": null,
  "available_actions": ["UNDER_MAINTENANCE", "OUT_OF_SERVICE", "RETIRED"],
  "attributes": {
    "refrigerant_type": "R-134a",
    "cooling_capacity_tons": 500,
    "oil_type": "Polyolester"
  },
  "created_at": "2026-11-16T04:22:15.890123Z",
  "updated_at": "2026-11-16T04:22:15.890123Z"
}
```

---

## 4. Controlled Status Transition API (`POST /api/v1/assets/{id}/transition/`)

- **Required Permission:** `asset.transition`
- **Request Body:**
```json
{
  "status": "UNDER_MAINTENANCE",
  "reason": "Scheduled quarterly compressor overhaul and refrigerant leak inspection"
}
```
- **Response (200 OK):**
```json
{
  "status": "success",
  "asset_id": "e45f914b-2d71-49a3-a75d-6c17245b084a",
  "from_status": "ACTIVE",
  "to_status": "UNDER_MAINTENANCE",
  "changed_at": "2026-11-16T04:22:30.120450Z"
}
```

