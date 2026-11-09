import uuid
import pytest
from django.template.loader import render_to_string
from django.test import Client

class MockWO:
    pk = uuid.uuid4()
    order_number = "WO-0001"
    work_type = "CORRECTIVE"
    status = "DRAFT"
    def get_status_display(self):
        return "Draft"

class MockForm:
    fields = {}
    is_hidden = False
    non_field_errors = lambda self: []
    def __iter__(self):
        return iter([])

def test_compile_action_template():
    out = render_to_string("workorder/action.html", {
        "operation": "Plan",
        "wo": MockWO(),
        "form": MockForm(),
        "expected_version": 1,
    })
    assert "Plan" in out

def test_compile_component_list_template():
    out = render_to_string("assets/component_list.html", {"filters": {}, "sites": []})
    assert "Component &amp; Spare Parts Catalog" in out

def test_compile_agreements_template():
    out = render_to_string("contracts/agreements.html", {"filters": {}})
    assert "agreements" in out.lower()

@pytest.mark.django_db
def test_http_work_order_plan_view(client, org_a, site_a1, owner_a):
    from apps.workorders.models import WorkOrder
    client.force_login(owner_a)
    s = client.session
    s["active_org_id"] = str(org_a.id)
    s.save()

    wo = WorkOrder.objects.create(
        organization=org_a,
        site=site_a1,
        title="Draft Test Order",
        description="Testing plan view",
        order_number="WO-PLAN-001",
        status=WorkOrder.Status.DRAFT,
        work_type=WorkOrder.WorkType.CORRECTIVE,
        priority=WorkOrder.Priority.MEDIUM,
        created_by=owner_a,
    )

    resp = client.get(f"/app/work-orders/{wo.pk}/plan/")
    assert resp.status_code == 200
    assert "Plan" in resp.content.decode()

@pytest.mark.django_db
def test_http_component_list_view(client, org_a, site_a1, owner_a):
    client.force_login(owner_a)
    s = client.session
    s["active_org_id"] = str(org_a.id)
    s.save()

    resp = client.get("/app/assets/components/")
    assert resp.status_code == 200
    assert "Component &amp; Spare Parts Catalog" in resp.content.decode()
