from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.core.net import is_suppressed_test_email

from . import services


@shared_task(name="apps.accounts.tasks.send_invitation_email", autoretry_for=(OSError,), retry_backoff=True,
             max_retries=5)
def send_invitation_email(user_id: str, org_id: str, new_account: bool):
    from apps.tenancy.models import Organization

    user = get_user_model().objects.get(pk=user_id)
    org = Organization.objects.get(pk=org_id)

    # Safety guard for QA/smoke testing: suppress outbound SMTP delivery for reserved test domains
    if is_suppressed_test_email(user.email):
        return

    ctx = {
        "user": user, "organization": org, "new_account": new_account,
        "action_url": services.activation_url(user) if new_account and not user.has_usable_password()
        else settings.SITE_BASE_URL.rstrip("/") + "/",
    }
    send_mail(
        subject=f"You've been invited to {org.name} on FieldOps Nexus",
        message=render_to_string("accounts/email/invitation.txt", ctx),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
