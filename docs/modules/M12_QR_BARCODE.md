# M12 QR & Barcode Physical Identification — Technical Specification & Module Guide

Part of the ONE integrated FieldOps Nexus ERP. Read `docs/PROJECT_SOURCE_OF_TRUTH.md` and `docs/FIELDOPS_NEXUS_MASTER_BUSINESS_WORKFLOW.md` first.

- **Module Code:** M12
- **Django Application:** `apps.identification`
- **HPE PRD Scope Reference:** Section 7.2 (REQ-ID-01: Asset identification via QR code and barcode generation, progressive web scanning, and secure context resolution)
- **Architectural Decision Reference:** Decision `D-050` (Opaque high-entropy identifiers without exposed primary keys)
- **Status:** 🟢 **FINALIZED, VERIFIED & PRODUCTION SIGNED-OFF**
- **Authoritative Ownership:** `AssetIdentifier`, `ScanEvent`, Label Generation (`segno`, `python-barcode`), Scanning Context Resolvers.

---

## 1. Purpose & Business Architecture

The QR & Barcode Physical Identification module bridges physical machinery in the field to the digital FieldOps Nexus platform. By affixing machine-readable industrial labels to equipment, field technicians, machine operators, and external clients can scan an asset with standard mobile devices to immediately:
1. Verify asset identity and location before starting high-voltage or hazardous service work.
2. View equipment maintenance dossiers, active work orders, and safety manuals.
3. Instantly initiate a new service incident request directly tied to the scanned asset.

---

## 2. Security Architecture & Decision D-050

Under Architectural Decision **`D-050`**, physical QR codes and barcodes must **never expose sensitive internal primary keys, sequential asset IDs, or tenant identifiers**. 

### 2.1 Security Controls Implemented
1. **Opaque High-Entropy Tokens:** Every physical identifier encodes a cryptographically secure random 64-character URL-safe token generated via `secrets.token_urlsafe(32)`.
2. **Zero Information Leakage:** Even if an unauthorized party scans a physical tag, the payload reveals no internal database IDs, organization slugs, or serial numbers.
3. **One-Click Token Invalidation & Replacement:** If a physical asset tag is damaged, scraped, or compromised, authorized personnel can revoke or regenerate the token without modifying the underlying asset record.
4. **Scan Telemetry & Audit Trails:** Every scan event is recorded in `ScanEvent` capturing actor, timestamp, client IP, user agent, and resolved action.

---

## 3. Data Model Architecture (`src/apps/identification/models.py`)

1. **`AssetIdentifier`:**
   - Authoritative mapping between an `Asset` and physical identification tokens.
   - Fields: `organization`, `asset`, `kind` (`QR`, `BARCODE`), `token` (unique alphanumeric string), `is_active`, `revoked_at`, `revoked_reason`, `created_at`.
   - Invariants:
     - An asset can possess active QR and Barcode identifiers simultaneously.
     - Tokens are globally unique across all organizations.
     - Revocation is append-only with timestamp and audit tracking.

2. **`ScanEvent`:**
   - Telemetry audit entity recording scan interactions.
   - Fields: `organization`, `asset`, `identifier`, `scanned_by` (FK `User`, nullable for anonymous portal scans), `ip_address`, `user_agent`, `notes`, `created_at`.

---

## 4. Supported Formats & Graphic Rendering Engine

The backend generates vector and raster image formats dynamically without third-party external cloud dependencies:

- **QR Codes:** Generated using `segno` supporting ECC Level M (15% error correction) and Level Q (25% error correction for industrial harsh environments).
- **1D Barcodes:** Generated using `python-barcode` supporting standard **Code 128** formatting.
- **Rendering Endpoints:**
  - `GET /app/assets/{id}/labels/qr/svg/` — Scalable Vector Graphics for industrial laser engraving and precision label printing.
  - `GET /app/assets/{id}/labels/qr/png/` — High-DPI raster image for on-screen display and badge export.
  - `GET /app/assets/{id}/labels/barcode/svg/` — Code128 vector barcode.
  - `GET /app/assets/{id}/labels/barcode/png/` — Code128 raster barcode.
  - `GET /app/assets/{id}/label/` — Printable industrial label sheet formatted for Brother and Zebra thermal printers.

---

## 5. Web Scanner & Progressive Scan Resolution Flow

```
[Mobile Device / Camera Scanner]
              │
              v
[Scan Token URL: /app/s/<token>/]
              │
              ├── Authenticated Staff User?
              │         │
              │         ├── Yes ──> Redirect to /app/assets/<asset_id>/ (Full Asset Profile)
              │         │
              │         └── No ───> Redirect to /accounts/login/?next=/app/s/<token>/
              │
              └── Public / Portal Incident Flow: /app/s/<token>/report/
                        │
                        └── Pre-fills Service Request Form with Verified Asset Link
```

---

## 6. Security & RBAC Enforcement

| Permission Code | Description | Role Assignments |
| :--- | :--- | :--- |
| `qr.view` | View generated QR/Barcode labels, download SVGs/PNGs | All internal staff roles, Client (scoped) |
| `qr.generate` | Generate, replace, or revoke physical asset tokens | Organization Owner, Asset Manager, Technician |
| `asset.view` | Resolve scanned token to full asset profile | Internal staff with site permission |
| `incident.create` | Initiate service request from scanned token | All internal staff, Portal Client |

---

## 7. User Interface Views

- **Asset Detail "Labels" Tab (`LabelPanelView`):** Live side-by-side preview of QR Code and Code 128 barcode, one-click print button, download SVG/PNG links, and token replacement modal.
- **Mobile Scanner Cockpit (`/app/identification/scan/`):** Fullscreen responsive HTML5 camera stream using `Html5QrcodeScanner` with torch control and automatic target bounding boxes.
- **Scan Resolution Router (`/app/s/<token>/`):** Opaque token lookup that records telemetry and redirects to the asset detail view or service report form.

---

## 8. Verification & Quality Assurance Traceability

- **Automated Pytest Coverage:** `tests/test_m12_identification.py` (21 passing tests), `tests/test_client_portal_qr_scan.py`, `tests/test_scan_to_incident.py`.
- **REST API Test Specifications:** See `docs/testing/M12_API_TEST_REPORT.md` (10/10 Automated Endpoint Tests Passed).
- **Formal Sign-Off Certification:** See `docs/SITE_ASSET_QR_FINAL_ACCEPTANCE_SIGNOFF_REPORT.md`.
