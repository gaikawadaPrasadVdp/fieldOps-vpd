"""Organization + membership lifecycle (service layer: validation, transactions, audit)."""
from __future__ import annotations

import re
import uuid
import zoneinfo

from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.core.exceptions import Conflict, NotFound, PermissionDenied, ValidationFailed
from apps.rbac import services as rbac
from apps.rbac.models import Role

from .models import Membership, Organization

User = get_user_model()
_ORG_FIELDS = ["name", "legal_name", "timezone", "country", "contact_email", "contact_phone", "address"]


def _check_email(email: str) -> str:
    email = (email or "").strip().lower()
    if len(email) > 254:
        raise ValidationFailed("Email address cannot exceed 254 characters.", details={"email": email})
    try:
        validate_email(email)
    except Exception as exc:
        raise ValidationFailed("Enter a valid email address.", details={"email": email}) from exc
    return email


def _check_timezone(tz: str):
    try:
        zoneinfo.ZoneInfo(tz)
    except Exception as exc:
        raise ValidationFailed(f"Unknown timezone '{tz}'.") from exc


# --- organizations (platform level) ---------------------------------------------------------


@transaction.atomic
def create_organization(*, name, owner_email, owner_name, actor=None, slug=None, timezone_name="UTC",
                        country="", contact_email="", request=None, owner_password="FieldOps@2026!") -> tuple[Organization, Membership]:
    """Enterprise onboarding: creates the org, seeds system roles, invites the initial Owner."""
    if actor is not None and not (actor.is_superuser or actor.is_staff or getattr(actor, "is_platform_admin", False)):
        raise PermissionDenied("Only administrators can create organizations.")
    name = (name or "").strip()
    if len(name) < 2:
        raise ValidationFailed("Organization name is required.")
    _check_timezone(timezone_name)
    owner_email = _check_email(owner_email)
    slug = (slug or Organization.make_slug(name)).strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,58}[a-z0-9]", slug):
        raise ValidationFailed("Slug must be 3-60 chars: lowercase letters, digits and hyphens.")
    try:
        with transaction.atomic():
            org = Organization.objects.create(
                name=name, slug=slug, timezone=timezone_name, country=country.upper()[:2],
                contact_email=contact_email, created_by=actor,
            )
    except IntegrityError as exc:
        raise Conflict("An organization with this name or slug already exists.", code="duplicate_organization") from exc
    roles = rbac.seed_system_roles(org)
    audit.record("organization.created", actor=actor, organization=org, target=org,
                 after=audit.snapshot(org, _ORG_FIELDS + ["slug", "status"]), request=request)
    membership = _invite(org, email=owner_email, full_name=owner_name, roles=[roles["owner"]],
                         invited_by=actor, request=request, system=True, password=owner_password)
    return org, membership


@transaction.atomic
def set_organization_status(org: Organization, *, active: bool, actor=None, reason: str = "", request=None):
    if actor is not None and not (actor.is_superuser or actor.is_staff or getattr(actor, "is_platform_admin", False)):
        raise PermissionDenied("Only administrators can change organization status.")
    target = Organization.Status.ACTIVE if active else Organization.Status.SUSPENDED
    if org.status == target:
        raise Conflict(f"Organization is already {target.lower()}.", code="no_change")
    if not active and not reason.strip():
        raise ValidationFailed("A reason is required to suspend an organization.")
    before = {"status": org.status, "suspended_reason": org.suspended_reason}
    org.status = target
    org.suspended_reason = "" if active else reason.strip()[:300]
    org.save(update_fields=["status", "suspended_reason", "updated_at"])
    if active:
        Membership.objects.filter(organization=org, status=Membership.Status.SUSPENDED).update(
            status=Membership.Status.ACTIVE
        )
    else:
        Membership.objects.filter(organization=org, status=Membership.Status.ACTIVE).update(
            status=Membership.Status.SUSPENDED
        )
    audit.record("organization.activated" if active else "organization.suspended", actor=actor,
                 organization=org, target=org, before=before,
                 after={"status": org.status, "suspended_reason": org.suspended_reason}, request=request)


@transaction.atomic
def update_organization(org: Organization, *, actor, request=None, **changes) -> Organization:
    allowed = {k: v for k, v in changes.items() if k in _ORG_FIELDS}
    if "name" in allowed and len(allowed["name"].strip()) < 2:
        raise ValidationFailed("Organization name is required.")
    if "timezone" in allowed:
        _check_timezone(allowed["timezone"])
    before = audit.snapshot(org, _ORG_FIELDS)
    for k, v in allowed.items():
        setattr(org, k, v.strip() if isinstance(v, str) else v)
    try:
        with transaction.atomic():
            org.save()
    except IntegrityError as exc:
        raise Conflict("An organization with this name already exists.", code="duplicate_organization") from exc
    audit.record("organization.updated", actor=actor, organization=org, target=org, before=before,
                 after=audit.snapshot(org, _ORG_FIELDS), request=request)
    return org


def schedule_organization_deletion(org: Organization, *, days: int, reason: str, actor, request=None) -> Organization:
    """Platform Admin schedules an organization for deletion after `days` days."""
    if actor is not None and not (actor.is_superuser or actor.is_staff or getattr(actor, "is_platform_admin", False)):
        raise PermissionDenied("Only platform administrators can schedule organization deletions.")

    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 0

    if days < 1:
        raise ValidationFailed("Grace period must be at least 1 day.")

    reason = (reason or "").strip()
    if not reason:
        raise ValidationFailed("A reason for scheduling deletion is required.")

    from datetime import timedelta
    now = timezone.now()
    scheduled_at = now + timedelta(days=days)

    before = {
        "deletion_scheduled_at": str(org.deletion_scheduled_at) if org.deletion_scheduled_at else None,
        "deletion_reason": org.deletion_reason,
        "deletion_grace_days": org.deletion_grace_days,
    }

    org.deletion_scheduled_at = scheduled_at
    org.deletion_reason = reason[:500]
    org.deletion_grace_days = days
    org.deletion_requested_by = actor
    org.save(update_fields=["deletion_scheduled_at", "deletion_reason", "deletion_grace_days", "deletion_requested_by", "updated_at"])

    audit.record(
        "organization.deletion_scheduled",
        actor=actor,
        organization=org,
        target=org,
        target_repr=f"Organization {org.name} ({org.pk})",
        before=before,
        after={
            "deletion_scheduled_at": str(scheduled_at),
            "deletion_reason": org.deletion_reason,
            "deletion_grace_days": days,
        },
        request=request,
    )
    return org


def cancel_organization_deletion(org: Organization, *, actor, request=None) -> Organization:
    """Platform Admin cancels a scheduled organization deletion."""
    if actor is not None and not (actor.is_superuser or actor.is_staff or getattr(actor, "is_platform_admin", False)):
        raise PermissionDenied("Only platform administrators can cancel scheduled deletions.")

    if not org.deletion_scheduled_at:
        raise Conflict("This organization does not have a scheduled deletion.", code="no_scheduled_deletion")

    before = {
        "deletion_scheduled_at": str(org.deletion_scheduled_at),
        "deletion_reason": org.deletion_reason,
        "deletion_grace_days": org.deletion_grace_days,
    }

    org.deletion_scheduled_at = None
    org.deletion_reason = ""
    org.deletion_grace_days = 0
    org.deletion_requested_by = None
    org.save(update_fields=["deletion_scheduled_at", "deletion_reason", "deletion_grace_days", "deletion_requested_by", "updated_at"])

    audit.record(
        "organization.deletion_cancelled",
        actor=actor,
        organization=org,
        target=org,
        target_repr=f"Organization {org.name} ({org.pk})",
        before=before,
        after={"deletion_scheduled_at": None, "deletion_reason": ""},
        request=request,
    )
    return org


def process_due_scheduled_deletions() -> int:
    """Executes permanent deletion for organizations whose scheduled deletion date has arrived."""
    due_orgs = Organization.objects.filter(
        deletion_scheduled_at__lte=timezone.now(),
    )
    count = 0
    for org in due_orgs:
        try:
            permanently_delete_organization(org, actor=org.deletion_requested_by, reason=org.deletion_reason)
            count += 1
        except Exception:
            pass
    return count


def permanently_delete_organization(org: Organization, *, actor, reason: str = "", request=None) -> tuple[bool, str]:
    """Permanently and immediately deletes an organization and all its tenant-scoped records from the database."""
    if actor is not None and not (actor.is_superuser or actor.is_staff or getattr(actor, "is_platform_admin", False)):
        raise PermissionDenied("Only platform administrators can delete organizations.")

    from django.db import connection, transaction

    org_name = org.name
    org_id = str(org.pk)
    del_reason = (reason or org.deletion_reason or "").strip()

    audit.record(
        "organization.permanently_deleted",
        actor=actor,
        organization=org,
        target=org,
        target_repr=f"Organization {org_name} ({org_id})",
        before={"name": org.name, "status": org.status, "slug": org.slug, "reason": del_reason},
        request=request,
    )

    tenant_tables = [
        'workspace_travellog', 'workspace_worknote',
        'workorders_workordersignoff', 'workorders_closureapproval',
        'workorders_workorderevidence', 'workorders_workordermaterial',
        'workorders_workorderlabor', 'workorders_workorderassignment',
        'workorders_workorderevent', 'workorders_workorder',
        'portal_portalclosureconfirmation', 'portal_portalassetgrant',
        'portal_portalaccount',
        'sla_slapauseevent', 'sla_slabreach', 'sla_slaevent',
        'sla_slatracking', 'sla_slatarget', 'sla_escalationrule', 'sla_slaprofile',
        'notifications_notification', 'identification_scanevent',
        'identification_assetidentifier', 'contracts_coveredasset',
        'contracts_coverageexclusion', 'contracts_coveragecheck',
        'contracts_coverageagreement', 'contracts_serviceprovider',
        'incidents_servicerequesthistory', 'incidents_downtime', 'incidents_servicerequest',
        'inventory_partreservation', 'inventory_stockmovement', 'inventory_workorderpart',
        'inventory_stockbalance', 'inventory_part', 'inventory_warehouse',
        'checklists_inspectionresponse', 'checklists_finding', 'checklists_inspection',
        'checklists_checklistitem', 'checklists_checklisttemplate',
        'maintenance_maintenancecycle', 'maintenance_maintenanceschedule', 'maintenance_maintenanceplan',
        'assets_assetstatushistory', 'assets_assetmeterreading', 'assets_assetmeter',
        'assets_assetlocationhistory', 'assets_assetdocument', 'assets_assetcomponent',
        'assets_asset', 'assets_assetcategory', 'files_attachment',
        'sites_calendarholiday', 'sites_zone', 'sites_sitecontact',
        'sites_operatingcalendar', 'sites_site',
        'rbac_membershiprole', 'rbac_role',
        'core_documentsequence', 'audit_auditlog',
        'tenancy_membership',
        'tenancy_organization'
    ]

    with transaction.atomic():
        with connection.cursor() as cur:
            if connection.vendor == 'postgresql':
                cur.execute("SET session_replication_role = 'replica';")
            try:
                for tbl in tenant_tables:
                    if tbl == 'tenancy_organization':
                        cur.execute(f"DELETE FROM {tbl} WHERE id = %s", [org_id])
                    elif tbl == 'rbac_membershiprole':
                        cur.execute(
                            f"DELETE FROM {tbl} WHERE membership_id IN (SELECT id FROM tenancy_membership WHERE organization_id = %s)",
                            [org_id]
                        )
                    else:
                        cur.execute(f"DELETE FROM {tbl} WHERE organization_id = %s", [org_id])
            finally:
                if connection.vendor == 'postgresql':
                    cur.execute("SET session_replication_role = 'origin';")

    return True, f"Organization '{org_name}' permanently deleted."


@transaction.atomic
def delete_organization(org: Organization, *, actor, reason: str = "", request=None) -> tuple[bool, str]:
    """Platform Admin organization deletion / decommissioning.

    Attempts hard-delete when safe (no protected foreign keys). If the organization
    holds historical records, transactions, or audit logs, safely decommissions it:
    locks the tenant, deactivates active memberships, and sets status to SUSPENDED,
    preserving full data integrity and compliance trails (D-012/D-029).
    """
    if actor is not None and not (actor.is_superuser or actor.is_staff or getattr(actor, "is_platform_admin", False)):
        raise PermissionDenied("Only platform administrators can delete organizations.")

    from django.db.models import ProtectedError

    org_name = org.name
    org_id = str(org.pk)
    del_reason = (reason or org.deletion_reason or "").strip()

    audit.record(
        "organization.deleted",
        actor=actor,
        organization=org,
        target=org,
        target_repr=f"Organization {org_name} ({org_id})",
        before={"name": org.name, "status": org.status, "slug": org.slug, "reason": del_reason},
        request=request,
    )

    try:
        with transaction.atomic():
            org.delete()
        return True, f"Organization '{org_name}' permanently deleted."
    except (ProtectedError, IntegrityError):
        Membership.objects.filter(organization=org, status=Membership.Status.ACTIVE).update(
            status=Membership.Status.SUSPENDED
        )
        actor_label = getattr(actor, "full_name", None) or getattr(actor, "email", "platform admin")
        org.status = Organization.Status.SUSPENDED
        now_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        if del_reason:
            org.suspended_reason = f"Deleted/Decommissioned by {actor_label} on {now_str}. Reason: {del_reason}"[:300]
        else:
            org.suspended_reason = f"Deleted/Decommissioned by {actor_label} on {now_str}"[:300]
        org.deletion_scheduled_at = None
        org.deletion_grace_days = 0
        org.save(update_fields=["status", "suspended_reason", "deletion_scheduled_at", "deletion_grace_days", "updated_at"])
        return False, f"Organization '{org_name}' contains protected historical records and was safely decommissioned (suspended and locked)."


# --- members ---------------------------------------------------------------------------------


def _invite(org, *, email, full_name, roles, invited_by, request=None, system=False,
            assignments=None, password=None) -> Membership:
    from apps.accounts import services as accounts

    email = _check_email(email)
    full_name = (full_name or "").strip()
    user = User.objects.filter(email__iexact=email).first()
    created_user = False
    if user is None:
        if not full_name:
            full_name = email.split("@")[0].replace(".", " ").title()
        user = User.objects.create_user(email=email, password=password, full_name=full_name)
        created_user = True
    elif password and not user.has_usable_password():
        user.set_password(password)
        user.save()

    if Membership.objects.unscoped().filter(user=user, organization=org).exists():
        raise Conflict(f"This user ({user.email}) is already a member of this organization. You can view or edit their roles in the Users list.", code="already_member")

    is_direct = bool(password or user.has_usable_password())
    status = Membership.Status.ACTIVE if is_direct else Membership.Status.INVITED
    membership = Membership(
        organization=org, user=user, status=status, invited_by=invited_by,
        activated_at=timezone.now() if status == Membership.Status.ACTIVE else None,
    )
    membership.save()
    assignments = assignments if assignments is not None else [(r, None) for r in roles]
    rbac.set_membership_assignments(membership, assignments, actor=invited_by, request=request, system=system)
    audit.record("user.created" if is_direct else "user.invited", actor=invited_by, organization=org, target=membership,
                 target_repr=f"{user.email} @ {org.slug}",
                 after={"email": user.email, "status": status, "roles": sorted(rbac._describe(r, st) for r, st in assignments),
                        "new_account": created_user}, request=request)

    try:
        from apps.portal.models import PortalAccount, PortalAssetGrant
        from apps.ui.utils import is_client_membership
        if is_client_membership(membership) or any(getattr(r, "system_key", None) == "client_requester" for r in roles):
            portal_acc, _ = PortalAccount.objects.unscoped().get_or_create(
                organization=org,
                membership=membership,
                defaults={
                    "company_name": full_name or org.name,
                    "is_enabled": True,
                },
            )
            from apps.assets.models import Asset
            assets_qs = Asset.objects.for_organization(org).exclude(status__in=["RETIRED", "DISPOSED"])
            site_ids = [s.pk for _, s in assignments if s is not None]
            if site_ids:
                assets_qs = assets_qs.filter(site_id__in=site_ids)
            for asset in assets_qs:
                PortalAssetGrant.objects.unscoped().get_or_create(
                    organization=org,
                    portal_account=portal_acc,
                    asset=asset,
                )
    except Exception:
        pass

    if not is_direct:
        accounts.queue_invitation_email(user, org, membership, new_account=created_user)

    return membership


def resolve_assignments(org, *, role_ids=None, site_ids=None, assignments=None) -> list:
    """Turns client input into validated [(Role, Site | None)] for ``org``.

    ``assignments`` = [{"role_id", "site_id" | None}]; otherwise every role in ``role_ids`` is granted for each
    site in ``site_ids`` (or organization-wide when no sites are given). Roles and sites must belong to ``org``."""
    from apps.sites.models import Site

    if assignments is not None:
        pairs = [(a["role_id"], a.get("site_id")) for a in assignments]
    else:
        sites = list(dict.fromkeys(site_ids or [])) or [None]
        pairs = [(rid, sid) for rid in dict.fromkeys(role_ids or []) for sid in sites]
    role_keys = {rid for rid, _ in pairs}
    site_keys = {sid for _, sid in pairs if sid is not None}
    roles = {r.pk: r for r in Role.objects.unscoped().filter(organization=org, pk__in=role_keys)}
    if len(roles) != len(role_keys):
        raise ValidationFailed("One or more roles are invalid for this organization.", code="invalid_roles")
    sites = {x.pk: x for x in Site.objects.unscoped().filter(organization=org, pk__in=site_keys)}
    if len(sites) != len(site_keys):
        raise ValidationFailed("One or more sites are invalid for this organization.", code="invalid_sites")
    out = []
    for rid, sid in pairs:
        if sid is not None and roles[rid].is_owner:
            raise ValidationFailed("The Owner role cannot be limited to a site.", code="owner_not_site_scoped")
        out.append((roles[rid], sites[sid] if sid is not None else None))
    return out


@transaction.atomic
def invite_member(org, *, email, full_name, role_ids=None, actor, request=None, site_ids=None,
                  assignments=None, password=None) -> Membership:
    resolved = resolve_assignments(org, role_ids=role_ids, site_ids=site_ids, assignments=assignments)
    if not resolved:
        raise ValidationFailed("Assign at least one role.", code="roles_required")
    return _invite(org, email=email, full_name=full_name, roles=[r for r, _ in resolved], invited_by=actor,
                   request=request, assignments=resolved, password=password)


@transaction.atomic
def resend_invitation(membership: Membership, *, actor, request=None):
    from apps.accounts import services as accounts

    if membership.status != Membership.Status.INVITED:
        raise Conflict("Only pending invitations can be re-sent.", code="not_pending")
    audit.record("user.invitation_resent", actor=actor, organization=membership.organization,
                 target=membership, target_repr=membership.user.email, request=request)
    accounts.queue_invitation_email(membership.user, membership.organization, membership, new_account=True)


@transaction.atomic
def update_member(membership: Membership, *, actor, full_name=None, job_title=None, role_ids=None, request=None,
                  site_ids=None, assignments=None):
    user = membership.user
    before = {"full_name": user.full_name, "job_title": membership.job_title}
    if full_name is not None:
        if not full_name.strip():
            raise ValidationFailed("Full name is required.")
        user.full_name = full_name.strip()
        user.save(update_fields=["full_name"])
    if job_title is not None:
        membership.job_title = job_title.strip()
        membership.save(update_fields=["job_title", "updated_at"])
    if role_ids is not None or assignments is not None:
        resolved = resolve_assignments(membership.organization, role_ids=role_ids, site_ids=site_ids,
                                       assignments=assignments)
        if not resolved:
            raise ValidationFailed("Assign at least one valid role.", code="invalid_roles")
        rbac.set_membership_assignments(membership, resolved, actor=actor, request=request)
        try:
            from apps.portal.models import PortalAccount, PortalAssetGrant
            from apps.ui.utils import is_client_membership
            if is_client_membership(membership):
                portal_acc, _ = PortalAccount.objects.unscoped().get_or_create(
                    organization=membership.organization,
                    membership=membership,
                    defaults={
                        "company_name": membership.user.full_name or membership.organization.name,
                        "is_enabled": True,
                    },
                )
                from apps.assets.models import Asset
                assets_qs = Asset.objects.for_organization(membership.organization).exclude(status__in=["RETIRED", "DISPOSED"])
                site_ids = [s.pk for _, s in resolved if s is not None]
                if site_ids:
                    assets_qs = assets_qs.filter(site_id__in=site_ids)
                for asset in assets_qs:
                    PortalAssetGrant.objects.unscoped().get_or_create(
                        organization=membership.organization,
                        portal_account=portal_acc,
                        asset=asset,
                    )
        except Exception:
            pass
    after = {"full_name": user.full_name, "job_title": membership.job_title}
    if before != after:
        audit.record("user.updated", actor=actor, organization=membership.organization, target=membership,
                     target_repr=user.email, before=before, after=after, request=request)


@transaction.atomic
def add_role_assignment(membership: Membership, *, role_id, site_id=None, actor, request=None):
    """Adds one role (organization-wide, or for one site) without touching the other assignments."""
    current = [(mr.role, mr.site) for mr in membership.membership_roles.select_related("role", "site")]
    new = resolve_assignments(membership.organization, assignments=[{"role_id": role_id, "site_id": site_id}])
    rbac.set_membership_assignments(membership, current + new, actor=actor, request=request)


@transaction.atomic
def remove_role_assignment(membership: Membership, *, assignment_id, actor, request=None):
    mrs = list(membership.membership_roles.select_related("role", "site"))
    keep = [(mr.role, mr.site) for mr in mrs if str(mr.pk) != str(assignment_id)]
    if len(keep) == len(mrs):
        raise NotFound("Role assignment not found.")
    if not keep:
        raise ValidationFailed("A member must keep at least one role; deactivate the member instead.",
                               code="roles_required")
    rbac.set_membership_assignments(membership, keep, actor=actor, request=request)


@transaction.atomic
def set_member_active(membership: Membership, *, active: bool, actor, request=None):
    if membership.user_id == getattr(actor, "pk", None):
        raise Conflict("You cannot change your own access.", code="self_change")
    target = Membership.Status.ACTIVE if active else Membership.Status.SUSPENDED
    if membership.status == target:
        raise Conflict(f"Member is already {target.lower()}.", code="no_change")
    if membership.status == Membership.Status.INVITED and active:
        raise Conflict("Pending invitations are activated by the user.", code="not_activated")
    if not active:
        rbac.assert_not_last_owner(membership)
    before = {"status": membership.status}
    membership.status = target
    if active and membership.activated_at is None:
        membership.activated_at = timezone.now()
    rbac.clear_cache(membership)
    membership.save(update_fields=["status", "activated_at", "updated_at"])
    audit.record("user.reactivated" if active else "user.deactivated", actor=actor,
                 organization=membership.organization, target=membership, target_repr=membership.user.email,
                 before=before, after={"status": membership.status}, request=request)


def get_membership(org, pk) -> Membership:
    try:
        pk = uuid.UUID(str(pk))
    except ValueError as exc:
        raise NotFound("Member not found.") from exc
    m = Membership.objects.unscoped().filter(organization=org, pk=pk).select_related("user").first()
    if m is None:
        raise NotFound("Member not found.")
    return m
