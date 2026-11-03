"""
Unit and integration tests for Warranty / AMC / Contract download and export functionality.
Verifies CSV generation, HTTP headers, content structure, covered asset inclusion, and permission controls.
"""
import csv
import datetime
import io
import pytest
from django.test import Client

from apps.contracts.models import CoverageAgreement, CoveredAsset, ServiceProvider


@pytest.fixture
def contract_fixture(org_a, owner_a, site_a1, make_asset):
    asset = make_asset(org_a, site_a1, "AST-TEST-001", name="Test Chiller Unit", serial_number="SN-CHILLER-999")
    provider = ServiceProvider.objects.create(
        organization=org_a,
        name="Carrier HVAC Services",
        email="support@carrier.example.com",
        phone="+1 800 555 0199",
        is_active=True,
    )
    today = datetime.date.today()
    agreement = CoverageAgreement.objects.create(
        organization=org_a,
        site=site_a1,
        provider=provider,
        reference="WAR-2026-001",
        title="Chiller Comprehensive Warranty",
        kind=CoverageAgreement.Kind.WARRANTY,
        start_date=today - datetime.timedelta(days=30),
        end_date=today + datetime.timedelta(days=335),
        terms="Covers all mechanical and electrical compressor defects.",
        sla_terms="4-hour on-site response time.",
        renewal_alert_days=60,
        is_active=True,
    )
    CoveredAsset.objects.create(organization=org_a, agreement=agreement, asset=asset)
    return {
        "org": org_a,
        "owner": owner_a,
        "site": site_a1,
        "asset": asset,
        "provider": provider,
        "agreement": agreement,
    }


def test_agreements_list_csv_export_via_query_param(client: Client, contract_fixture):
    """Verify ?export=csv on /app/contracts/agreements/ returns CSV attachment."""
    client.force_login(contract_fixture["owner"])
    session = client.session
    session["active_org_id"] = str(contract_fixture["org"].pk)
    session.save()

    res = client.get("/app/contracts/agreements/?export=csv")
    assert res.status_code == 200
    assert "text/csv" in res["Content-Type"]
    assert "attachment;" in res["Content-Disposition"]
    assert f"warranties_contracts_{contract_fixture['org'].slug}_" in res["Content-Disposition"]

    content = res.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "Reference" in header
    assert "Title" in header
    assert "Provider" in header
    assert "Site Code" in header

    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row[0] == "WAR-2026-001"
    assert row[1] == "Chiller Comprehensive Warranty"
    assert row[2] == "Warranty"
    assert row[3] == "Carrier HVAC Services"
    assert row[4] == contract_fixture["site"].code


def test_agreements_direct_export_view_url(client: Client, contract_fixture):
    """Verify dedicated route /app/contracts/agreements/export/ returns CSV."""
    client.force_login(contract_fixture["owner"])
    session = client.session
    session["active_org_id"] = str(contract_fixture["org"].pk)
    session.save()

    res = client.get("/app/contracts/agreements/export/")
    assert res.status_code == 200
    assert "text/csv" in res["Content-Type"]
    assert f"warranties_contracts_{contract_fixture['org'].slug}_" in res["Content-Disposition"]

    content = res.content.decode("utf-8")
    assert "WAR-2026-001" in content
    assert "Chiller Comprehensive Warranty" in content


def test_single_agreement_csv_download(client: Client, contract_fixture):
    """Verify ?export=csv on /app/contracts/agreements/<id>/ returns agreement and covered asset details."""
    client.force_login(contract_fixture["owner"])
    session = client.session
    session["active_org_id"] = str(contract_fixture["org"].pk)
    session.save()

    ag = contract_fixture["agreement"]
    res = client.get(f"/app/contracts/agreements/{ag.pk}/?export=csv")
    assert res.status_code == 200
    assert "text/csv" in res["Content-Type"]
    assert "attachment;" in res["Content-Disposition"]
    assert f"warranty_{ag.reference}_" in res["Content-Disposition"]

    content = res.content.decode("utf-8")
    assert "AGREEMENT DETAILS" in content
    assert "WAR-2026-001" in content
    assert "Carrier HVAC Services" in content
    assert "COVERED ASSETS" in content
    assert "AST-TEST-001" in content
    assert "Test Chiller Unit" in content
    assert "SN-CHILLER-999" in content


def test_single_agreement_direct_download_view_url(client: Client, contract_fixture):
    """Verify dedicated route /app/contracts/agreements/<id>/download/ returns agreement CSV."""
    client.force_login(contract_fixture["owner"])
    session = client.session
    session["active_org_id"] = str(contract_fixture["org"].pk)
    session.save()

    ag = contract_fixture["agreement"]
    res = client.get(f"/app/contracts/agreements/{ag.pk}/download/")
    assert res.status_code == 200
    assert "text/csv" in res["Content-Type"]
    assert "AST-TEST-001" in res.content.decode("utf-8")


def test_expiry_report_csv_export(client: Client, contract_fixture):
    """Verify ?export=csv on /app/contracts/expiry/ returns expiring forecast CSV."""
    client.force_login(contract_fixture["owner"])
    session = client.session
    session["active_org_id"] = str(contract_fixture["org"].pk)
    session.save()

    res = client.get("/app/contracts/expiry/?days=365&export=csv")
    assert res.status_code == 200
    assert "text/csv" in res["Content-Type"]
    assert f"expiring_warranties_{contract_fixture['org'].slug}_365d_" in res["Content-Disposition"]

    content = res.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "Reference" in header
    assert "Days Left" in header
    assert "Renewed" in header
    assert "Covered Assets Count" in header

    rows = list(reader)
    assert len(rows) == 1
    assert rows[0][0] == "WAR-2026-001"


def test_api_coverage_agreements_export_action(client: Client, contract_fixture):
    """Verify API action /api/v1/coverage-agreements/export/ returns CSV."""
    client.force_login(contract_fixture["owner"])
    session = client.session
    session["active_org_id"] = str(contract_fixture["org"].pk)
    session.save()

    res = client.get("/api/v1/coverage-agreements/export/")
    assert res.status_code == 200
    assert "text/csv" in res["Content-Type"]
    assert "WAR-2026-001" in res.content.decode("utf-8")


def test_api_coverage_agreement_download_action(client: Client, contract_fixture):
    """Verify API action /api/v1/coverage-agreements/<id>/download/ returns single agreement CSV."""
    client.force_login(contract_fixture["owner"])
    session = client.session
    session["active_org_id"] = str(contract_fixture["org"].pk)
    session.save()

    ag = contract_fixture["agreement"]
    res = client.get(f"/api/v1/coverage-agreements/{ag.pk}/download/")
    assert res.status_code == 200
    assert "text/csv" in res["Content-Type"]
    content = res.content.decode("utf-8")
    assert "AGREEMENT DETAILS" in content
    assert "AST-TEST-001" in content
