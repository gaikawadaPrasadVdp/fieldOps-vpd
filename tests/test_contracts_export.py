import csv
import datetime
import io
import openpyxl
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.contracts import exports, services as contract_services
from apps.contracts.models import CoverageAgreement

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def site_a(org_a, make_site):
    return make_site(org_a, "SITE-A1")


@pytest.fixture
def provider_a(org_a, owner_a):
    return contract_services.create_provider(
        org_a,
        name="Global HVAC Services",
        contact_name="Alice Smith",
        email="alice@hvac.test",
        phone="+1-555-0199",
        actor=owner_a,
    )


@pytest.fixture
def asset_a1(org_a, site_a, make_asset):
    return make_asset(
        org_a,
        site_a,
        "PUMP-01",
        name="Main Coolant Pump",
        manufacturer="Grundfos",
        model="CR-95",
        serial_number="SN-GR-9921",
    )


@pytest.fixture
def asset_a2(org_a, site_a, make_asset):
    return make_asset(
        org_a,
        site_a,
        "PUMP-02",
        name="Auxiliary Coolant Pump",
        manufacturer="Grundfos",
        model="CR-90",
        serial_number="SN-GR-9922",
    )


@pytest.fixture
def agreements_fixture(org_a, site_a, provider_a, asset_a1, asset_a2, owner_a):
    ag1 = contract_services.create_agreement(
        org_a,
        kind="WARRANTY",
        reference="WAR-2026-001",
        title="Primary Coolant Pump Warranty",
        provider=provider_a,
        site=site_a,
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 12, 31),
        assets=[asset_a1],
        terms="Covers parts and on-site labor for defects.",
        exclusion_notes="Excludes accidental physical damage.",
        sla_terms="Next business day response.",
        actor=owner_a,
    )
    ag2 = contract_services.create_agreement(
        org_a,
        kind="AMC",
        reference="AMC-2026-002",
        title="Plant Annual Maintenance Contract",
        provider=provider_a,
        site=site_a,
        start_date=datetime.date(2026, 2, 1),
        end_date=datetime.date(2027, 1, 31),
        assets=[asset_a2],
        terms="Routine annual preventive servicing.",
        actor=owner_a,
    )
    return [ag1, ag2]


def _login_ui(client, user, org):
    client.force_login(user)
    session = client.session
    session["organization_id"] = str(org.pk)
    session.save()


# ==============================================================================
# 1. BULK EXPORT TESTS (CSV, Excel, PDF)
# ==============================================================================

def test_warranty_csv_bulk_export(client, org_a, owner_a, agreements_fixture):
    """Test successful CSV bulk export with proper headers and data."""
    _login_ui(client, owner_a, org_a)
    response = client.get("/app/contracts/agreements/export/?format=csv")
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]
    assert 'attachment; filename="warranties_export_alpha-industries_' in response["Content-Disposition"]

    content = response.content.decode("utf-8-sig")  # strip BOM
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "Warranty Reference" in header
    assert "Title" in header
    assert "Covered Asset Tags" in header
    assert "Asset Serial Numbers" in header
    assert "Coverage Terms" in header

    rows = list(reader)
    assert len(rows) == 2
    refs = [r[0] for r in rows]
    assert "WAR-2026-001" in refs
    assert "AMC-2026-002" in refs

    # Check that asset details are populated
    war_row = next(r for r in rows if r[0] == "WAR-2026-001")
    assert "PUMP-01" in war_row[header.index("Covered Asset Tags")]
    assert "Main Coolant Pump" in war_row[header.index("Covered Asset Names")]
    assert "SN-GR-9921" in war_row[header.index("Asset Serial Numbers")]
    assert "Grundfos" in war_row[header.index("Asset Manufacturers")]
    assert "CR-95" in war_row[header.index("Asset Models")]


def test_warranty_list_export_param_csv(client, org_a, owner_a, agreements_fixture):
    """Test that GET /app/contracts/agreements/?export=csv also triggers CSV download."""
    _login_ui(client, owner_a, org_a)
    response = client.get("/app/contracts/agreements/?export=csv")
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]
    assert "WAR-2026-001" in response.content.decode("utf-8-sig")


def test_warranty_excel_bulk_export(client, org_a, owner_a, agreements_fixture):
    """Test successful Excel (.xlsx) bulk export with formatted workbook."""
    _login_ui(client, owner_a, org_a)
    response = client.get("/app/contracts/agreements/export/?format=xlsx")
    assert response.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response["Content-Type"]
    assert response["Content-Disposition"].endswith('.xlsx"')

    wb = openpyxl.load_workbook(io.BytesIO(response.content))
    assert "Warranty Details" in wb.sheetnames
    assert "Export Information" in wb.sheetnames

    ws = wb["Warranty Details"]
    assert ws.cell(row=1, column=1).value == "Warranty Reference"
    assert ws.cell(row=1, column=2).value == "Title"
    assert ws.max_row == 3  # Header + 2 agreements


def test_warranty_pdf_bulk_export(client, org_a, owner_a, agreements_fixture):
    """Test bulk PDF report export."""
    _login_ui(client, owner_a, org_a)
    response = client.get("/app/contracts/agreements/export/?format=pdf")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


# ==============================================================================
# 2. INDIVIDUAL WARRANTY PDF DOWNLOAD TESTS
# ==============================================================================

def test_individual_warranty_pdf_download(client, org_a, owner_a, agreements_fixture):
    """Test downloading an individual warranty generates a separate valid PDF."""
    _login_ui(client, owner_a, org_a)
    ag1, ag2 = agreements_fixture

    resp1 = client.get(f"/app/contracts/agreements/{ag1.pk}/download/")
    assert resp1.status_code == 200
    assert resp1["Content-Type"] == "application/pdf"
    assert 'attachment; filename="Warranty_WAR-2026-001_' in resp1["Content-Disposition"]
    assert resp1.content.startswith(b"%PDF")

    resp2 = client.get(f"/app/contracts/agreements/{ag2.pk}/download/")
    assert resp2.status_code == 200
    assert 'attachment; filename="Warranty_AMC-2026-002_' in resp2["Content-Disposition"]

    # Verify separate individual documents
    assert resp1.content != resp2.content
    assert len(resp1.content) > 1000
    assert len(resp2.content) > 1000


# ==============================================================================
# 3. DRF API ENDPOINT TESTS (/api/v1/coverage-agreements/ & /api/v1/warranties/)
# ==============================================================================

def test_api_bulk_export_and_alias(as_user, org_a, owner_a, agreements_fixture):
    """Test REST API bulk export on both coverage-agreements and warranties routes."""
    api = as_user(owner_a, org_a)

    # Primary route
    res1 = api.get("/api/v1/coverage-agreements/export/?format=csv")
    print("STATUS:", res1.status_code, "DATA:", getattr(res1, "data", res1.content))
    assert res1.status_code == 200
    assert "text/csv" in res1["Content-Type"]
    assert "WAR-2026-001" in res1.content.decode("utf-8-sig")

    # Excel format
    res_xlsx = api.get("/api/v1/coverage-agreements/export/?format=xlsx")
    assert res_xlsx.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res_xlsx["Content-Type"]

    # Warranties alias route
    res_alias = api.get("/api/v1/warranties/export/?format=csv")
    assert res_alias.status_code == 200
    assert "text/csv" in res_alias["Content-Type"]


def test_api_individual_download(as_user, org_a, owner_a, agreements_fixture):
    """Test REST API individual warranty download."""
    api = as_user(owner_a, org_a)
    ag1 = agreements_fixture[0]

    # Primary route
    res = api.get(f"/api/v1/coverage-agreements/{ag1.pk}/download/")
    assert res.status_code == 200
    assert res["Content-Type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")

    # Warranties alias route
    res_alias = api.get(f"/api/v1/warranties/{ag1.pk}/download/")
    assert res_alias.status_code == 200
    assert res_alias["Content-Type"] == "application/pdf"


# ==============================================================================
# 4. PAGINATION & FILTER TESTS (EXPORT ALL MATCHING, NOT JUST PAGE 1)
# ==============================================================================

def test_export_all_records_across_pages(client, org_a, site_a, provider_a, make_asset, owner_a):
    """Test that all matching records across pagination boundaries are exported."""
    _login_ui(client, owner_a, org_a)

    # Create 22 agreements (default pagination size is 20)
    for i in range(1, 23):
        asset = make_asset(org_a, site_a, f"PAGE-ASSET-{i:03d}")
        contract_services.create_agreement(
            org_a,
            kind="WARRANTY",
            reference=f"WAR-PAGED-{i:03d}",
            title=f"Paged Warranty {i}",
            provider=provider_a,
            site=site_a,
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            assets=[asset],
            actor=owner_a,
        )

    # Regular list returns 20 on page 1
    resp_list = client.get("/app/contracts/agreements/")
    assert len(resp_list.context["page"]) == 20

    # Bulk export returns all 22 records
    resp_export = client.get("/app/contracts/agreements/export/?format=csv")
    content = resp_export.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(content)))
    # 1 header + 22 data rows
    assert len(rows) == 23


def test_export_respects_active_filters(client, org_a, site_a, provider_a, make_asset, owner_a):
    """Test filtering by query, kind, and status during export."""
    _login_ui(client, owner_a, org_a)

    asset1 = make_asset(org_a, site_a, "GEN-ASSET-01")
    asset2 = make_asset(org_a, site_a, "PUMP-ASSET-02")

    contract_services.create_agreement(
        org_a,
        kind="WARRANTY",
        reference="WAR-FILTER-MATCH",
        title="Specific Generator Coverage",
        provider=provider_a,
        site=site_a,
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 12, 31),
        assets=[asset1],
        actor=owner_a,
    )
    contract_services.create_agreement(
        org_a,
        kind="AMC",
        reference="AMC-OTHER",
        title="Other Service",
        provider=provider_a,
        site=site_a,
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 12, 31),
        assets=[asset2],
        actor=owner_a,
    )

    # Filter by search term
    resp = client.get("/app/contracts/agreements/export/?format=csv&q=Generator")
    content = resp.content.decode("utf-8-sig")
    assert "WAR-FILTER-MATCH" in content
    assert "AMC-OTHER" not in content

    # Filter by kind
    resp_kind = client.get("/app/contracts/agreements/export/?format=csv&kind=AMC")
    content_kind = resp_kind.content.decode("utf-8-sig")
    assert "AMC-OTHER" in content_kind
    assert "WAR-FILTER-MATCH" not in content_kind


def test_empty_result_sets(client, org_a, owner_a):
    """Test exporting when no records match returns valid file with headers only."""
    _login_ui(client, owner_a, org_a)
    resp = client.get("/app/contracts/agreements/export/?format=csv&q=nonexistent_match_string")
    assert resp.status_code == 200
    content = resp.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(content)))
    assert len(rows) == 1  # Header only


# ==============================================================================
# 5. SECURITY & PERMISSION TESTS
# ==============================================================================

def test_unauthorized_cross_tenant_access(as_user, org_a, org_b, owner_a, owner_b, agreements_fixture):
    """Verify tenant isolation: users from Org B cannot download Org A's warranties."""
    ag_a = agreements_fixture[0]
    api_b = as_user(owner_b, org_b)

    # Try downloading Org A warranty
    res = api_b.get(f"/api/v1/coverage-agreements/{ag_a.pk}/download/")
    assert res.status_code in (403, 404)

    # Try bulk export in Org B context - should not see Org A records
    res_bulk = api_b.get("/api/v1/coverage-agreements/export/?format=csv")
    assert "WAR-2026-001" not in res_bulk.content.decode("utf-8-sig")


def test_invalid_export_format_rejected(client, as_user, org_a, owner_a, agreements_fixture):
    """Verify invalid format returns 400 Bad Request."""
    _login_ui(client, owner_a, org_a)
    r_ui = client.get("/app/contracts/agreements/export/?format=unsupported_ext")
    assert r_ui.status_code == 400

    api = as_user(owner_a, org_a)
    r_api = api.get("/api/v1/coverage-agreements/export/?format=unsupported_ext")
    assert r_api.status_code == 400


# ==============================================================================
# 6. AUDIT LOGGING & UI RENDERING VERIFICATION
# ==============================================================================

def test_export_and_download_audit_logged(client, org_a, owner_a, agreements_fixture):
    """Verify that export and download events write audit logs."""
    _login_ui(client, owner_a, org_a)
    ag1 = agreements_fixture[0]

    client.get("/app/contracts/agreements/export/?format=csv")
    client.get(f"/app/contracts/agreements/{ag1.pk}/download/")

    actions = list(AuditLog.objects.filter(organization=org_a).values_list("action", flat=True))
    assert "contract.exported" in actions
    assert "contract.downloaded" in actions


def test_ui_templates_render_download_actions(client, org_a, owner_a, agreements_fixture):
    """Verify the Download / Export button and table row download links are present in HTML."""
    _login_ui(client, owner_a, org_a)
    ag1 = agreements_fixture[0]

    # Listing page
    r_list = client.get("/app/contracts/agreements/")
    assert r_list.status_code == 200
    html_list = r_list.content.decode("utf-8")
    assert "warrantyExportDropdown" in html_list
    assert "Download / Export" in html_list
    assert "handleWarrantyExport(event, 'csv')" in html_list
    assert f"/app/contracts/agreements/{ag1.pk}/download/" in html_list

    # Details page
    r_detail = client.get(f"/app/contracts/agreements/{ag1.pk}/")
    assert r_detail.status_code == 200
    html_detail = r_detail.content.decode("utf-8")
    assert f"/app/contracts/agreements/{ag1.pk}/download/" in html_detail
    assert "Download PDF" in html_detail
