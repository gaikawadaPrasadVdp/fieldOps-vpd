"""Account lifecycle: invitation/activation tokens + emails, membership activation, password events."""
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.audit import services as audit

logger = logging.getLogger(__name__)


def _safe_delay_invitation(user_id: str, org_id: str, new_account: bool):
    from .tasks import send_invitation_email

    try:
        send_invitation_email.delay(user_id, org_id, new_account)
    except Exception:
        logger.exception("Failed to queue invitation email for user=%s org=%s", user_id, org_id)


def activation_url(user) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse("accounts:activate", kwargs={"uidb64": uid, "token": token})
    return f"{settings.SITE_BASE_URL.rstrip('/')}{path}"


def password_reset_url(user) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse("accounts:password_reset_confirm", kwargs={"uidb64": uid, "token": token})
    return f"{settings.SITE_BASE_URL.rstrip('/')}{path}"


def queue_invitation_email(user, org, membership, *, new_account: bool):
    user_id, org_id = str(user.pk), str(org.pk)
    transaction.on_commit(lambda: _safe_delay_invitation(user_id, org_id, new_account))


@transaction.atomic
def activate_pending_memberships(user, *, request=None) -> int:
    """Called when an invited user sets their password: INVITED -> ACTIVE across organizations."""
    from apps.tenancy.models import Membership

    pending = Membership.objects.unscoped().filter(user=user, status=Membership.Status.INVITED)
    count = 0
    for m in pending.select_related("organization"):
        m.status = Membership.Status.ACTIVE
        m.activated_at = timezone.now()
        m.save(update_fields=["status", "activated_at", "updated_at"])
        audit.record("user.activated", actor=user, organization=m.organization, target=m,
                     target_repr=user.email, after={"status": m.status}, request=request)
        count += 1
    return count
