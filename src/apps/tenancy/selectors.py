"""Tenant resolution: which organization is this authenticated user acting in?

This module (and rbac.services / tenancy.services) are the only places allowed to use
``Manager.unscoped()``: they are the trusted bridge between identity and tenant context."""
from __future__ import annotations

import uuid
from django.db import models

from apps.core.exceptions import PermissionDenied

from .models import Membership, Organization

SESSION_KEY = "active_org_id"


def active_memberships(user):
    return (
        Membership.objects.unscoped()
        .filter(user=user, status=Membership.Status.ACTIVE)
        .select_related("organization")
        .order_by("organization__name")
    )


def resolve_membership(user, *, org_key: str | None = None, session_org_id: str | None = None, candidates=None):
    """Returns the active Membership for this request, or None if the user has not chosen/cannot be
    defaulted. Raises PermissionDenied for explicit-but-invalid selections and suspended organizations.
    ``candidates`` lets a caller that already loaded the user's active memberships avoid a second query."""
    if user is None or not user.is_authenticated:
        return None
    if candidates is None:
        candidates = list(active_memberships(user))
    chosen = None
    if org_key:
        chosen = next((m for m in candidates if m.organization.slug == org_key or str(m.organization_id) == org_key), None)
        if chosen is None:
            lookup = models.Q(organization__slug=org_key)
            try:
                lookup |= models.Q(organization_id=uuid.UUID(str(org_key)))
            except ValueError:
                pass
            existing_m = Membership.objects.unscoped().filter(lookup, user=user).select_related("organization").first()
            if existing_m is not None:
                if existing_m.organization.status != Organization.Status.ACTIVE:
                    raise PermissionDenied("This organization is suspended.", code="organization_suspended")
                if existing_m.status == Membership.Status.SUSPENDED:
                    raise PermissionDenied("Your membership in this organization is suspended.", code="membership_suspended")
            raise PermissionDenied("You are not a member of this organization.", code="not_a_member")
    elif session_org_id:
        chosen = next((m for m in candidates if str(m.organization_id) == str(session_org_id)), None)
        if chosen is None:
            try:
                existing_m = Membership.objects.unscoped().filter(organization_id=uuid.UUID(str(session_org_id)), user=user).select_related("organization").first()
                if existing_m is not None:
                    if existing_m.organization.status != Organization.Status.ACTIVE:
                        raise PermissionDenied("This organization is suspended.", code="organization_suspended")
                    if existing_m.status == Membership.Status.SUSPENDED:
                        raise PermissionDenied("Your membership in this organization is suspended.", code="membership_suspended")
            except ValueError:
                pass
    if chosen is None and len(candidates) == 1:
        chosen = candidates[0]
    if chosen is None and not candidates:
        existing_m = Membership.objects.unscoped().filter(user=user).select_related("organization").first()
        if existing_m is not None:
            if existing_m.organization.status != Organization.Status.ACTIVE:
                raise PermissionDenied("This organization is suspended.", code="organization_suspended")
            if existing_m.status == Membership.Status.SUSPENDED:
                raise PermissionDenied("Your membership in this organization is suspended.", code="membership_suspended")
    if chosen is not None and chosen.organization.status != Organization.Status.ACTIVE:
        raise PermissionDenied("This organization is suspended.", code="organization_suspended")
    return chosen


def organization_members(org):
    return (
        Membership.objects.unscoped()
        .filter(organization=org)
        .select_related("user")
        .prefetch_related("membership_roles__role", "membership_roles__site")
    )


def is_organization_member(user, org) -> bool:
    if not user or not org:
        return False
    return Membership.objects.unscoped().filter(user=user, organization=org).exists()
