"""M13 Client / Requester portal permissions."""
from apps.rbac.catalog import register

register("portal", "portal.request.create", "Submit client service requests through the portal", site_scoped=True)
register("portal", "portal.request.view", "View own client portal requests and dashboard", site_scoped=True)
register("portal", "portal.request.confirm", "Confirm resolution or request rework on own portal requests", site_scoped=True)
register("portal", "portal.manage", "Manage client portal accounts and access")
