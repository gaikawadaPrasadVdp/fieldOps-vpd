from __future__ import annotations

from django.db import models, transaction

import logging
import uuid

logger = logging.getLogger(__name__)

from apps.assets.models import Asset
from apps.audit import services as audit
from apps.core import tenant
from apps.core.exceptions import Conflict, NotFound, PermissionDenied, ValidationFailed
from apps.incidents import services as incident_services
from apps.incidents.models import ServiceRequest
from apps.rbac import services as rbac
from apps.sites.models import Site
from apps.tenancy.models import Membership, Organization

from .models import PortalAccount, PortalAssetGrant, PortalClosureConfirmation
from .selectors import get_linked_work_order, get_portal_account, is_asset_granted_to_client

CLIENT_ALLOWED_INCIDENT_PERMS = {
    "incident.report_owned",
    "incident.view_owned",
    "incident.view_assigned",
    "incident.attach",
    "incident.confirm",
}


def _is_uuid(val) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError):
        return False


def verify_portal_access(membership: Membership | None) -> PortalAccount:
    """Validates that a membership is authorized to access the Client Portal.

    Enforces:
    1. Active membership in the organization.
    2. Active user account.
    3. Portal permission (portal.request.view).
    4. Registered PortalAccount in the same organization.
    5. PortalAccount is enabled (is_enabled == True).

    Raises PermissionDenied if any requirement is not met.
    """
    if membership is None:
        raise PermissionDenied("Authentication and organization membership are required.")

    if not membership.is_active:
        if membership.status == Membership.Status.INVITED and membership.user.has_usable_password():
            membership.status = Membership.Status.ACTIVE
            membership.save(update_fields=["status", "updated_at"])
        else:
            raise PermissionDenied("Organization membership is not active.")

    if not membership.user.is_active:
        raise PermissionDenied("User account is inactive.")

    has_view = (
        rbac.has_permission(membership, "portal.request.view")
        or rbac.has_permission_anywhere(membership, "portal.request.view")
        or membership.membership_roles.filter(role__system_key="client_requester").exists()
    )
    if not has_view:
        raise PermissionDenied("Account lacks portal access permissions.")

    account = get_portal_account(membership)
    if account is None:
        raise PermissionDenied("No portal account registered for this membership.")

    if not account.is_enabled:
        raise PermissionDenied("Portal account has been disabled by an administrator.")

    if account.organization_id != membership.organization_id:
        raise PermissionDenied("Cross-organization portal access blocked.")

    return account


def verify_portal_request_create_access(membership: Membership | None) -> PortalAccount:
    """Validates that a membership is authorized to create service requests in the Client Portal.

    Enforces:
    1. verify_portal_access (active membership, active user, portal.request.view, enabled PortalAccount, matching org)
    2. Permission: portal.request.create
    """
    account = verify_portal_access(membership)
    has_create = (
        rbac.has_permission(membership, "portal.request.create")
        or rbac.has_permission_anywhere(membership, "portal.request.create")
    )
    if not has_create:
        raise PermissionDenied("Account lacks request creation permission.")
    return account


def verify_portal_request_confirm_access(membership: Membership | None) -> PortalAccount:
    """Validates that a membership is authorized to confirm closure of service requests.

    Enforces:
    1. verify_portal_access (active membership, active user, portal.request.view, enabled PortalAccount, matching org)
    2. Permission: portal.request.confirm
    """
    account = verify_portal_access(membership)
    has_confirm = (
        rbac.has_permission(membership, "portal.request.confirm")
        or rbac.has_permission_anywhere(membership, "portal.request.confirm")
    )
    if not has_confirm:
        raise PermissionDenied("Account lacks request confirmation permission.")
    return account


def is_portal_client(membership: Membership | None) -> bool:
    """Returns True if the membership has valid, enabled portal access."""
    try:
        verify_portal_access(membership)
        return True
    except PermissionDenied:
        return False


@transaction.atomic
def create_portal_service_request(
    membership: Membership,
    *,
    asset: Asset | uuid.UUID | str,
    title: str,
    description: str = "",
    kind: str = ServiceRequest.Kind.SERVICE_REQUEST,
    severity: str = ServiceRequest.Severity.MEDIUM,
    service_impact: str = ServiceRequest.Impact.NONE,
    impact_notes: str = "",
    site: Site | uuid.UUID | str | None = None,
    occurred_at=None,
    attachments=None,
    override_duplicate: bool = False,
    override_reason: str = "",
    actor=None,
    request=None,
) -> ServiceRequest:
    """Submits a new client service request against an authorized asset.

    Enforces:
    - Active and enabled PortalAccount with portal.request.create permission.
    - Tenant ownership of the target asset and optional site.
    - Asset is not terminal (RETIRED or DISPOSED).
    - If site is specified, asset must belong to that site.
    - Severity must be LOW, MEDIUM, or HIGH (clients cannot select CRITICAL).
    - Delegates creation to M05 incident service (preserving M05 sequence, SLA, audit, and lifecycle).
    - Stores file attachments if provided.
    - Emits portal.request_created audit record.
    """
    org = membership.organization
    account = verify_portal_request_create_access(membership)

    # Resolve and validate asset
    if isinstance(asset, (str, uuid.UUID)):
        asset_obj = Asset.objects.for_organization(org).filter(pk=asset).first()
        if not asset_obj:
            with tenant.platform_context():
                if Asset.objects.filter(pk=asset).exists():
                    raise ValidationFailed("Asset belongs to a different organization.", code="cross_tenant_asset")
            raise ValidationFailed("Asset not found in this organization.", code="asset_not_found")
        asset = asset_obj
    elif asset.organization_id != org.pk:
        raise ValidationFailed("Asset belongs to a different organization.", code="cross_tenant_asset")

    if asset.status in ("RETIRED", "DISPOSED"):
        raise Conflict("Retired or disposed assets cannot have new requests.", code="asset_terminal")

    # Enforce M13 Decision D-051: Client may only create requests for explicitly granted assets
    if not is_asset_granted_to_client(membership, asset.pk):
        raise ValidationFailed("Asset not found or not accessible.", code="asset_not_found")

    # Resolve and validate optional site
    if site is not None:
        if isinstance(site, (str, uuid.UUID)):
            site_obj = Site.objects.for_organization(org).filter(pk=site).first()
            if not site_obj:
                with tenant.platform_context():
                    if Site.objects.filter(pk=site).exists():
                        raise ValidationFailed("Site belongs to a different organization.", code="cross_tenant_site")
                raise ValidationFailed("Site not found in this organization.", code="site_not_found")
            site = site_obj
        elif site.organization_id != org.pk:
            raise ValidationFailed("Site belongs to a different organization.", code="cross_tenant_site")

        if asset.site_id != site.pk:
            raise ValidationFailed("Asset does not belong to the specified site.", code="asset_site_mismatch")

    # Severity validation: clients cannot select CRITICAL (staff triages urgency)
    if severity == ServiceRequest.Severity.CRITICAL:
        raise ValidationFailed(
            "Clients cannot select Critical severity. Requests will be triaged by service staff.",
            code="invalid_severity",
        )
    if severity not in (ServiceRequest.Severity.LOW, ServiceRequest.Severity.MEDIUM, ServiceRequest.Severity.HIGH):
        raise ValidationFailed("Unknown severity.", code="invalid_severity")

    # Call M05 incident services create_request
    sr = incident_services.create_request(
        org=org,
        asset=asset,
        reporter=membership,
        title=title,
        description=description,
        kind=kind,
        severity=severity,
        service_impact=service_impact,
        impact_notes=impact_notes,
        occurred_at=occurred_at,
        override_duplicate=override_duplicate,
        override_reason=override_reason,
        actor=actor or membership.user,
        request=request,
    )

    # Attach file evidence if provided
    if attachments:
        for uploaded in attachments:
            incident_services.add_evidence(
                sr,
                uploaded,
                actor=actor or membership.user,
                request=request,
            )

    # Record M13 portal audit entry
    audit.record(
        "portal.request_created",
        actor=actor or membership.user,
        organization=org,
        target=sr,
        after={
            "number": sr.number,
            "title": sr.title,
            "severity": sr.severity,
            "status": sr.status,
            "asset": asset.asset_tag,
        },
        metadata={"portal_account_id": str(account.pk)},
        request=request,
    )

    # Notify staff with incident.triage
    try:
        from apps.accounts.models import User
        from apps.notifications import services as notifications
        from apps.rbac.models import MembershipRole

        recipient_ids = (
            MembershipRole.objects.filter(
                membership__organization=org,
                membership__status=Membership.Status.ACTIVE,
                membership__user__is_active=True,
                role__role_permissions__permission__code="incident.triage",
            )
            .filter(models.Q(site__isnull=True) | models.Q(site=sr.site))
            .values_list("membership__user_id", flat=True)
            .distinct()
        )
        triage_recipients = list(User.objects.filter(pk__in=recipient_ids))
        if triage_recipients:
            notifications.notify(
                org,
                triage_recipients,
                title=f"New Service Request: {sr.number}",
                body=f"{sr.title} ({sr.severity}) submitted by {membership.user.display_name}",
                link=f"/app/incidents/{sr.pk}/",
                source="portal",
            )
    except Exception:
        logger.exception("Failed to notify staff of new portal service request %s", sr.number)

    return sr


def check_closure_confirmation_eligibility(membership: Membership, sr: ServiceRequest) -> tuple[bool, str]:
    """Evaluates whether a service request is eligible for client closure confirmation.

    Returns (is_eligible, reason_if_not_eligible).
    """
    if sr.organization_id != membership.organization_id:
        return False, "Request belongs to a different organization."

    if sr.reported_by_id != membership.pk:
        return False, "Only the requester who submitted the request can confirm its closure."

    has_confirm = (
        rbac.has_permission(membership, "portal.request.confirm")
        or rbac.has_permission_anywhere(membership, "portal.request.confirm")
    )
    if not has_confirm:
        return False, "User lacks portal.request.confirm permission."

    account = get_portal_account(membership)
    if not account or not account.is_enabled:
        return False, "Portal account is not active or enabled."

    # Check if already confirmed
    if getattr(sr, "closure_confirmation", None) is not None or PortalClosureConfirmation.objects.filter(request=sr).exists():
        return False, "This service request has already been confirmed."

    if sr.status in (ServiceRequest.Status.CONFIRMED, ServiceRequest.Status.CLOSED):
        return False, "This service request has already been confirmed."

    if sr.status == ServiceRequest.Status.REJECTED:
        return False, "Declined requests cannot be confirmed."

    if sr.status in (
        ServiceRequest.Status.NEW,
        ServiceRequest.Status.TRIAGED,
        ServiceRequest.Status.APPROVED,
        ServiceRequest.Status.WORK_ORDER_CREATED,
        ServiceRequest.Status.IN_SERVICE,
    ):
        return False, "Service is still in progress and cannot be confirmed prior to resolution."

    # Linked work order checks (mandatory supervisor review and approval)
    from apps.workorders.models import ClosureApproval, WorkOrder

    wo = get_linked_work_order(sr)
    if wo is not None:
        if wo.status == WorkOrder.Status.CANCELLED:
            return False, "The linked work order was cancelled."
        if wo.status != WorkOrder.Status.CLOSED:
            has_approval = wo.closure_approvals.filter(decision=ClosureApproval.Decision.APPROVED).exists()
            if not has_approval:
                return False, "Service completion requires supervisor review and approval before client confirmation."

    if sr.status != ServiceRequest.Status.RESOLVED:
        return False, f"Requests in status {sr.status} cannot be confirmed."

    return True, ""


def get_request_closure_blockers(sr: ServiceRequest) -> list[str]:
    """Evaluates whether any pending conditions prevent the service request from being transitioned to CLOSED.

    Returns a list of human-readable blocker messages explaining what is required before closure.
    """
    blockers = []

    # 1. State prerequisite: request must be in CONFIRMED or RESOLVED state
    if sr.status not in (
        ServiceRequest.Status.RESOLVED,
        ServiceRequest.Status.CONFIRMED,
        ServiceRequest.Status.CLOSED,
    ):
        blockers.append(f"Request is in '{sr.status}' state and must be resolved and confirmed before closure.")

    # 2. Client confirmation prerequisite
    has_conf = (
        getattr(sr, "closure_confirmation", None) is not None
        or PortalClosureConfirmation.objects.filter(request=sr).exists()
        or sr.confirmed_at is not None
    )
    if not has_conf and sr.status != ServiceRequest.Status.CLOSED:
        blockers.append("Client confirmation of service completion is required before closure.")

    # 3. Linked work order checks
    wo = get_linked_work_order(sr)
    if wo is not None:
        from apps.workorders.models import ClosureApproval, WorkOrder

        if wo.status == WorkOrder.Status.CANCELLED:
            blockers.append("Linked work order was cancelled.")
        elif wo.status in (
            WorkOrder.Status.DRAFT,
            WorkOrder.Status.PLANNED,
            WorkOrder.Status.ASSIGNED,
            WorkOrder.Status.DISPATCHED,
            WorkOrder.Status.IN_PROGRESS,
            WorkOrder.Status.ON_HOLD,
        ):
            blockers.append(f"Linked work order {wo.order_number} is still in progress ({wo.get_status_display()}).")
        elif wo.status in (WorkOrder.Status.COMPLETED, WorkOrder.Status.SUPERVISOR_REVIEW):
            has_approval = wo.closure_approvals.filter(decision=ClosureApproval.Decision.APPROVED).exists()
            if not has_approval:
                blockers.append(f"Supervisor quality review and approval is required on work order {wo.order_number}.")
            elif wo.status != WorkOrder.Status.CLOSED:
                blockers.append(f"Final closure of work order {wo.order_number} is pending.")

    return blockers


@transaction.atomic
def confirm_portal_request_closure(
    membership: Membership,
    request_id: str | uuid.UUID,
    *,
    feedback: str = "",
    rating: int | None = None,
    actor=None,
    request=None,
) -> PortalClosureConfirmation:
    """Confirms closure of a resolved service request by the authorized client requester.

    Enforces:
    - Active PortalAccount and organization membership.
    - portal.request.confirm permission.
    - Tenant isolation and requester ownership (anti-IDOR).
    - Status must be RESOLVED.
    - Mandatory supervisor approval on any linked work order.
    - Atomic persistence in PortalClosureConfirmation.
    - M05 lifecycle transition to CONFIRMED.
    - Automatic transition to CLOSED if all closure conditions are satisfied.
    - M15 audit records.
    """
    account = verify_portal_request_confirm_access(membership)

    from . import selectors
    sr = selectors.get_client_request(membership, request_id)
    if sr is None:
        raise NotFound("Service request not found.")

    eligible, reason = check_closure_confirmation_eligibility(membership, sr)
    if not eligible:
        if "already" in reason.lower():
            raise Conflict(reason, code="already_confirmed")
        if "supervisor" in reason.lower():
            raise Conflict(reason, code="supervisor_approval_required")
        if "in progress" in reason.lower() or "not been resolved" in reason.lower():
            raise Conflict(reason, code="incomplete_service")
        raise Conflict(reason, code="ineligible_for_confirmation")

    sr = ServiceRequest.objects.select_for_update().get(pk=sr.pk)
    if PortalClosureConfirmation.objects.filter(request=sr).exists() or sr.status in (
        ServiceRequest.Status.CONFIRMED,
        ServiceRequest.Status.CLOSED,
    ):
        raise Conflict("This service request has already been confirmed.", code="already_confirmed")

    wo = get_linked_work_order(sr)

    clean_feedback = (feedback or "").strip()[:1000]
    clean_rating = None
    if rating is not None and rating != "":
        try:
            r = int(rating)
            if 1 <= r <= 5:
                clean_rating = r
            else:
                raise ValidationFailed("Satisfaction rating must be an integer between 1 and 5.", code="invalid_rating")
        except (ValueError, TypeError):
            raise ValidationFailed("Satisfaction rating must be an integer between 1 and 5.", code="invalid_rating")

    confirmation = PortalClosureConfirmation(
        organization=sr.organization,
        request=sr,
        work_order=wo,
        portal_account=account,
        confirmed_by=actor or membership.user,
        rating=clean_rating,
        feedback=clean_feedback,
    )
    confirmation.save()

    # Ensure resolved_at is set if previously missing
    from django.utils import timezone
    if sr.resolved_at is None:
        sr.resolved_at = timezone.now()
        sr.save(update_fields=["resolved_at"])

    # Transition M05 service request to CONFIRMED
    sr = incident_services.transition(
        sr,
        action="confirm",
        reason=clean_feedback or "Client confirmed resolution",
        actor=actor or membership.user,
        request=request,
    )
    sr.refresh_from_db()
    confirmation.request = sr

    # Record M15 audit record for client confirmation
    audit.record(
        "portal.closure_confirmed",
        actor=actor or membership.user,
        organization=sr.organization,
        target=sr,
        after={
            "status": sr.status,
            "confirmed_at": confirmation.confirmed_at.isoformat(),
            "confirmed_by": (actor or membership.user).email,
            "rating": clean_rating,
            "feedback": clean_feedback,
            "work_order": wo.order_number if wo else None,
        },
        metadata={
            "portal_account_id": str(account.pk),
            "confirmation_id": str(confirmation.pk),
            "service_request_number": sr.number,
        },
        request=request,
    )

    # Check whether all required closure conditions are satisfied to transition to CLOSED automatically
    blockers = get_request_closure_blockers(sr)
    if not blockers and sr.status == ServiceRequest.Status.CONFIRMED:
        # Automatic transition through existing M05 service layer to terminal CLOSED state
        sr = incident_services.transition(
            sr,
            action="close",
            reason=clean_feedback or "All closure conditions satisfied upon client confirmation",
            actor=actor or membership.user,
            request=request,
        )
        sr.refresh_from_db()
        confirmation.request = sr

        # Record audit log for request closure
        audit.record(
            "portal.request_closed",
            actor=actor or membership.user,
            organization=sr.organization,
            target=sr,
            after={
                "status": sr.status,
                "closed_at": sr.closed_at.isoformat() if sr.closed_at else None,
                "confirmed_at": confirmation.confirmed_at.isoformat(),
                "confirmed_by": (actor or membership.user).email,
            },
            metadata={
                "portal_account_id": str(account.pk),
                "confirmation_id": str(confirmation.pk),
                "service_request_number": sr.number,
                "automatic_closure": True,
            },
            request=request,
        )

    return confirmation


def check_reopen_eligibility(membership: Membership, sr: ServiceRequest) -> tuple[bool, str]:
    """Evaluates whether a service request is eligible to be reopened by a client.

    Returns (is_eligible, reason_if_not_eligible).
    """
    if sr.organization_id != membership.organization_id:
        return False, "Request belongs to a different organization."

    if sr.reported_by_id != membership.pk:
        return False, "Only the requester who submitted the request can reopen it."

    has_perm = (
        rbac.has_permission_anywhere(membership, "portal.request.confirm")
        or rbac.has_permission_anywhere(membership, "portal.request.view")
        or membership.membership_roles.filter(role__system_key="client_requester").exists()
    )
    if not has_perm:
        return False, "User lacks portal permission to reopen requests."

    account = get_portal_account(membership)
    if not account or not account.is_enabled:
        return False, "Portal account is not active or enabled."

    if sr.status != ServiceRequest.Status.RESOLVED:
        if sr.status in (ServiceRequest.Status.CONFIRMED, ServiceRequest.Status.CLOSED):
            return False, "Confirmed or closed requests cannot be reopened."
        if sr.status == ServiceRequest.Status.REJECTED:
            return False, "Declined requests cannot be reopened."
        return False, f"Requests in status {sr.status} cannot be reopened (must be in RESOLVED status)."

    return True, ""


@transaction.atomic
def reopen_portal_service_request(
    membership: Membership,
    request_id: str | uuid.UUID,
    *,
    reason: str,
    actor=None,
    request=None,
) -> ServiceRequest:
    """Reopens a resolved service request by the authorized client requester.

    Enforces:
    - Active PortalAccount and organization membership.
    - Tenant isolation and requester ownership (anti-IDOR).
    - Status must be RESOLVED.
    - Mandatory non-empty reason (minimum 3 characters).
    - M05 lifecycle transition to APPROVED (rework path per D-035 and D-051).
    - M15 audit record.
    - Notifies internal staff holding incident.triage / incident.approve.
    """
    verify_portal_access(membership)

    clean_reason = (reason or "").strip()
    if len(clean_reason) < 3:
        raise ValidationFailed("A reason is required to reopen the request (minimum 3 characters).", code="reason_required")

    from . import selectors
    sr = selectors.get_client_request(membership, request_id)
    if sr is None:
        raise NotFound("Service request not found.")

    eligible, err_reason = check_reopen_eligibility(membership, sr)
    if not eligible:
        raise Conflict(err_reason, code="ineligible_for_reopen")

    sr = ServiceRequest.objects.select_for_update().get(pk=sr.pk)
    if sr.status != ServiceRequest.Status.RESOLVED:
        raise Conflict(f"Requests in status {sr.status} cannot be reopened.", code="ineligible_for_reopen")

    # M05 lifecycle transition: RESOLVED -> APPROVED with reason
    sr = incident_services.transition(
        sr,
        action="reopen",
        reason=clean_reason,
        actor=actor or membership.user,
        request=request,
    )

    # Record M13 portal audit entry
    audit.record(
        "portal.request_reopened",
        actor=actor or membership.user,
        organization=sr.organization,
        target=sr,
        after={
            "number": sr.number,
            "status": sr.status,
            "reopen_reason": clean_reason[:500],
        },
        metadata={"reopened_by": membership.user.email},
        request=request,
    )

    # Notify internal staff with incident.triage / incident.approve
    try:
        from apps.accounts.models import User
        from apps.notifications import services as notifications
        from apps.rbac.models import MembershipRole

        recipient_ids = (
            MembershipRole.objects.filter(
                membership__organization=sr.organization,
                membership__status=Membership.Status.ACTIVE,
                membership__user__is_active=True,
                role__role_permissions__permission__code__in=("incident.triage", "incident.approve"),
            )
            .filter(models.Q(site__isnull=True) | models.Q(site=sr.site))
            .values_list("membership__user_id", flat=True)
            .distinct()
        )
        staff_recipients = list(User.objects.filter(pk__in=recipient_ids))
        if staff_recipients:
            notifications.notify(
                sr.organization,
                staff_recipients,
                title=f"Service Request Reopened: {sr.number}",
                body=f"{sr.title} reopened by client: {clean_reason[:200]}",
                link=f"/app/incidents/{sr.pk}/",
                source="portal",
            )
    except Exception:
        logger.exception("Failed to notify staff of reopened portal service request %s", sr.number)

    return sr


@transaction.atomic
def create_portal_account(
    organization: Organization,
    membership: Membership,
    company_name: str = "",
    is_enabled: bool = True,
    auto_grant_assets: bool = True,
    notes: str = "",
    actor=None,
) -> PortalAccount:
    """Creates a new PortalAccount for an organization member with audit logging."""
    if membership.organization_id != organization.pk:
        raise ValidationFailed("Membership does not belong to the specified organization.")

    if not membership.is_active:
        raise ValidationFailed("Cannot create a portal account for an inactive membership.")

    perms = rbac.membership_permissions(membership)
    non_client_perms = [
        p for p in perms
        if not (p.startswith("portal.request.") or p in CLIENT_ALLOWED_INCIDENT_PERMS)
    ]
    if non_client_perms:
        raise ValidationFailed("Portal accounts may only be provisioned for client-only memberships.", code="not_client_only")

    existing = PortalAccount.objects.for_organization(organization).filter(
        membership=membership,
    ).first()
    if existing:
        raise Conflict("A portal account already exists for this membership.")

    account = PortalAccount(
        organization=organization,
        membership=membership,
        company_name=company_name.strip(),
        is_enabled=is_enabled,
        auto_grant_assets=bool(auto_grant_assets),
        notes=notes.strip(),
    )
    account.save()

    if account.auto_grant_assets and account.is_enabled:
        sync_portal_grants_for_account(account)

    audit.record(
        "portal.account_created",
        actor=actor,
        organization=organization,
        target=account,
        after=audit.snapshot(account, ["company_name", "is_enabled", "auto_grant_assets", "notes"]),
        metadata={"membership_id": str(membership.pk), "user_email": membership.user.email},
    )
    return account


@transaction.atomic
def enable_portal_account(account: PortalAccount, actor=None) -> PortalAccount:
    """Enables a portal account and records an audit log entry."""
    perms = rbac.membership_permissions(account.membership)
    non_client_perms = [
        p for p in perms
        if not (p.startswith("portal.request.") or p in CLIENT_ALLOWED_INCIDENT_PERMS)
    ]
    if non_client_perms:
        raise Conflict("Only client-only members can have enabled portal accounts.", code="not_client_only")

    if not account.is_enabled:
        account.is_enabled = True
        account.save(update_fields=["is_enabled", "updated_at"])
        audit.record(
            "portal.account_enabled",
            actor=actor,
            organization=account.organization,
            target=account,
            after=audit.snapshot(account, ["is_enabled", "company_name"]),
            metadata={"user_email": account.membership.user.email},
        )
    return account


@transaction.atomic
def disable_portal_account(account: PortalAccount, actor=None) -> PortalAccount:
    """Disables a portal account and records an audit log entry."""
    if account.is_enabled:
        account.is_enabled = False
        account.save(update_fields=["is_enabled", "updated_at"])
        audit.record(
            "portal.account_disabled",
            actor=actor,
            organization=account.organization,
            target=account,
            after=audit.snapshot(account, ["is_enabled", "company_name"]),
            metadata={"user_email": account.membership.user.email},
        )
    return account


@transaction.atomic
def toggle_portal_account(account: PortalAccount, actor=None) -> PortalAccount:
    """Toggles the enabled status of a portal account."""
    if account.is_enabled:
        return disable_portal_account(account, actor=actor)
    return enable_portal_account(account, actor=actor)


@transaction.atomic
def update_portal_account(
    account: PortalAccount,
    *,
    company_name: str | None = None,
    notes: str | None = None,
    is_enabled: bool | None = None,
    auto_grant_assets: bool | None = None,
    actor=None,
) -> PortalAccount:
    """Updates portal account metadata with audit trail."""
    before = audit.snapshot(account, ["company_name", "notes", "is_enabled", "auto_grant_assets"])
    update_fields = ["updated_at"]

    if company_name is not None:
        account.company_name = company_name.strip()
        update_fields.append("company_name")

    if notes is not None:
        account.notes = notes.strip()
        update_fields.append("notes")

    if is_enabled is not None:
        account.is_enabled = bool(is_enabled)
        update_fields.append("is_enabled")

    if auto_grant_assets is not None:
        account.auto_grant_assets = bool(auto_grant_assets)
        update_fields.append("auto_grant_assets")

    account.save(update_fields=update_fields)

    if account.auto_grant_assets and account.is_enabled:
        sync_portal_grants_for_account(account)

    audit.record(
        "portal.account_updated",
        actor=actor,
        organization=account.organization,
        target=account,
        before=before,
        after=audit.snapshot(account, ["company_name", "notes", "is_enabled", "auto_grant_assets"]),
        metadata={"user_email": account.membership.user.email},
    )
    return account


@transaction.atomic
def grant_portal_asset(
    portal_account: PortalAccount,
    asset: Asset,
    actor=None,
) -> PortalAssetGrant:
    """Grants a client portal account access to report on a specific asset with audit logging."""
    if portal_account.organization_id != asset.organization_id:
        raise ValidationFailed("Cross-organization asset grant blocked.", code="cross_tenant_grant")
    if asset.status in ("RETIRED", "DISPOSED"):
        raise Conflict("Cannot grant access to retired or disposed assets.", code="asset_terminal")

    grant, created = PortalAssetGrant.objects.get_or_create(
        organization=portal_account.organization,
        portal_account=portal_account,
        asset=asset,
    )
    if created:
        audit.record(
            "portal.asset_granted",
            actor=actor,
            organization=portal_account.organization,
            target=grant,
            after={"asset_tag": asset.asset_tag, "portal_account_id": str(portal_account.pk)},
            metadata={"company_name": portal_account.company_name},
        )
    return grant


@transaction.atomic
def revoke_portal_asset(
    portal_account: PortalAccount,
    asset: Asset,
    actor=None,
) -> bool:
    """Revokes a client portal account's access to an asset with audit logging."""
    grant = PortalAssetGrant.objects.filter(
        organization=portal_account.organization,
        portal_account=portal_account,
        asset=asset,
    ).first()
    if grant:
        grant.delete()
        audit.record(
            "portal.asset_revoked",
            actor=actor,
            organization=portal_account.organization,
            target=grant,
            before={"asset_tag": asset.asset_tag, "portal_account_id": str(portal_account.pk)},
            metadata={"company_name": portal_account.company_name},
        )
        return True
    return False


def _portal_account_site_ids(account: PortalAccount) -> list[uuid.UUID] | None:
    """Returns allowed site IDs for a site-scoped client account, or None if org-wide."""
    site_ids = list(
        account.membership.membership_roles.values_list("site_id", flat=True)
    )
    if not site_ids or None in site_ids:
        return None
    return [sid for sid in site_ids if sid is not None]


@transaction.atomic
def sync_portal_grants_for_account(account: PortalAccount) -> int:
    """Grants all active organization (or site-scoped) assets to an auto-syncing PortalAccount."""
    if not account.is_enabled or not account.auto_grant_assets or not account.membership.is_active:
        return 0

    assets_qs = Asset.objects.for_organization(account.organization).exclude(
        status__in=["RETIRED", "DISPOSED"]
    )
    allowed_site_ids = _portal_account_site_ids(account)
    if allowed_site_ids is not None:
        assets_qs = assets_qs.filter(site_id__in=allowed_site_ids)

    granted = 0
    for asset in assets_qs:
        _, created = PortalAssetGrant.objects.get_or_create(
            organization=account.organization,
            portal_account=account,
            asset=asset,
        )
        if created:
            granted += 1
    return granted


@transaction.atomic
def sync_portal_grants_for_asset(asset: Asset, actor=None) -> int:
    """Syncs newly created or relocated active assets to enabled PortalAccounts with auto_grant_assets=True."""
    if asset.status in ("RETIRED", "DISPOSED"):
        return 0

    accounts = (
        PortalAccount.objects.for_organization(asset.organization_id)
        .filter(
            is_enabled=True,
            auto_grant_assets=True,
            membership__status=Membership.Status.ACTIVE,
            membership__user__is_active=True,
        )
        .select_related("membership")
    )
    granted = 0
    for account in accounts:
        allowed_site_ids = _portal_account_site_ids(account)
        if allowed_site_ids is not None and asset.site_id not in allowed_site_ids:
            continue
        _, created = PortalAssetGrant.objects.get_or_create(
            organization=asset.organization,
            portal_account=account,
            asset=asset,
        )
        if created:
            granted += 1
    return granted
