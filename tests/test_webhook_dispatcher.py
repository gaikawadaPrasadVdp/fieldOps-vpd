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
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None
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
        # urllib headers are capitalized in get_header
        assert req.get_header("X-fieldops-signature") is not None
        assert req.full_url == "https://crm.example.com/events/"

@pytest.mark.django_db
def test_inactive_webhook_is_not_called(org_a):
    endpoint = WebhookEndpoint.objects.create(
        organization=org_a,
        name="Inactive Webhook",
        target_url="https://crm.example.com/events/",
        secret_token="secret_key_123",
        event_pattern="*",
        is_active=False,
    )
    with patch("urllib.request.urlopen") as mock_url:
        event = publish_integration_event(
            org_a,
            event_type="work_order.completed",
            aggregate_type="work_order",
            aggregate_id="WO-0001",
            payload={"status": "COMPLETED"},
        )
        process_pending_events(batch_size=10)
        assert not mock_url.called

