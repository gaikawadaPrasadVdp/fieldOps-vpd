import pytest
from apps.core.models import IntegrationEvent, WebhookEndpoint

@pytest.mark.django_db
def test_integration_events_api_and_retry(as_user, owner_a, org_a):
    client = as_user(owner_a, org_a)
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
    results = res_list.data.get("results", res_list.data)
    assert any(str(e["id"]) == str(event.pk) for e in results)

    # Retry action endpoint
    res_retry = client.post(f"/api/v1/integration-events/{event.pk}/retry/")
    assert res_retry.status_code == 200
    event.refresh_from_db()
    assert event.status in [IntegrationEvent.Status.PENDING, IntegrationEvent.Status.PUBLISHED]
    assert event.retry_count == 0

@pytest.mark.django_db
def test_webhook_endpoints_api_crud(as_user, owner_a, org_a):
    client = as_user(owner_a, org_a)
    # Create Webhook Endpoint
    res_create = client.post("/api/v1/webhooks/", {
        "name": "ERP Webhook",
        "target_url": "https://erp.example.com/api/v1/events/",
        "secret_token": "erp_secret_token",
        "event_pattern": "work_order.*",
        "is_active": True,
    }, format="json")
    assert res_create.status_code == 201
    webhook_id = res_create.data["id"]

    # List Webhooks
    res_list = client.get("/api/v1/webhooks/")
    assert res_list.status_code == 200
    assert any(w["name"] == "ERP Webhook" for w in res_list.data.get("results", res_list.data))

