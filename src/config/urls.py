from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import SimpleRouter

from apps.assets.api_views import (
    AssetCategoryViewSet,
    AssetViewSet,
    ComponentViewSet,
    MeterViewSet,
)
from apps.audit.api_views import AuditLogViewSet
from apps.checklists.api_views import (
    ChecklistTemplateViewSet,
    FindingViewSet,
    InspectionViewSet,
)
from apps.contracts.api_views import (
    AgreementViewSet,
    CoverageCheckViewSet,
    CoverageViewSet,
    ProviderViewSet,
)
from apps.core import health
from apps.core.api_views import IntegrationEventViewSet, WebhookEndpointViewSet
from apps.identification.api_views import IdentifierViewSet
from apps.incidents.api_views import ServiceRequestViewSet
from apps.inventory.api_views import (
    PartReservationViewSet,
    PartViewSet,
    StockBalanceViewSet,
    StockMovementViewSet,
    WarehouseViewSet,
    WorkOrderPartViewSet,
)
from apps.maintenance.api_views import (
    MaintenanceCycleViewSet,
    MaintenancePlanViewSet,
    MaintenanceScheduleViewSet,
)
from apps.notifications.api_views import NotificationViewSet
from apps.portal.api_views import PortalAccountViewSet
from apps.rbac.api_views import PermissionViewSet, RoleViewSet
from apps.sites.api_views import (
    CalendarViewSet,
    ContactViewSet,
    HolidayViewSet,
    SiteViewSet,
    ZoneViewSet,
    ShiftViewSet,
)
from apps.sla.api_views import (
    EscalationViewSet,
    SLABreachViewSet,
    SLAMetricsView,
    SLAProfileViewSet,
    SLATrackingViewSet,
)
from apps.tenancy.api_views import MemberViewSet, OrganizationViewSet, PlatformOrganizationViewSet, PlatformUserViewSet
from apps.workorders.views import WorkOrderViewSet, TechnicianProfileViewSet

# Module teams: import your viewsets here and register them on the router.
router = SimpleRouter()
router.register("members", MemberViewSet, basename="member")
router.register("users", MemberViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")
router.register("audit-logs", AuditLogViewSet, basename="auditlog")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("sites", SiteViewSet, basename="site")
router.register("zones", ZoneViewSet, basename="zone")
router.register("shifts", ShiftViewSet, basename="shift")
router.register("technician-profiles", TechnicianProfileViewSet, basename="technician-profile")
router.register("calendars", CalendarViewSet, basename="calendar")
router.register("calendar-holidays", HolidayViewSet, basename="calendar-holiday")
router.register("site-contacts", ContactViewSet, basename="site-contact")
router.register("contacts", ContactViewSet, basename="contact")
router.register("assets", AssetViewSet, basename="asset")
router.register("asset-categories", AssetCategoryViewSet, basename="asset-category")
router.register("asset-components", ComponentViewSet, basename="asset-component")
router.register("asset-meters", MeterViewSet, basename="asset-meter")
router.register("asset-identifiers", IdentifierViewSet, basename="asset-identifier")
router.register("service-requests", ServiceRequestViewSet, basename="service-request")
router.register("requests", ServiceRequestViewSet, basename="requests")
router.register("contract-providers", ProviderViewSet, basename="contract-provider")
router.register("coverage-agreements", AgreementViewSet, basename="coverage-agreement")
router.register("warranties", AgreementViewSet, basename="warranty")
router.register("coverage-checks", CoverageCheckViewSet, basename="coverage-check")
router.register("coverage", CoverageViewSet, basename="coverage")
router.register("platform/organizations", PlatformOrganizationViewSet, basename="platform-organization")
router.register("sla-profiles", SLAProfileViewSet, basename="sla-profile")
router.register("slas", SLAProfileViewSet, basename="sla")
router.register("sla-trackings", SLATrackingViewSet, basename="sla-tracking")
router.register("sla-breaches", SLABreachViewSet, basename="sla-breach")
router.register("breaches", SLABreachViewSet, basename="breach")
router.register("escalations", EscalationViewSet, basename="escalation")
router.register("sla-escalations", EscalationViewSet, basename="sla-escalation")
router.register("maintenance-plans", MaintenancePlanViewSet, basename="maintenance-plan")
router.register("maintenance-schedules", MaintenanceScheduleViewSet, basename="maintenance-schedule")
router.register("maintenance-cycles", MaintenanceCycleViewSet, basename="maintenance-cycle")
router.register("portal-accounts", PortalAccountViewSet, basename="portal-account")
router.register("parts", PartViewSet, basename="part")
router.register("warehouses", WarehouseViewSet, basename="warehouse")
router.register("stock-balances", StockBalanceViewSet, basename="stock-balance")
router.register("stocks", StockBalanceViewSet, basename="stocks")
router.register("stock-movements", StockMovementViewSet, basename="stock-movement")
router.register("part-reservations", PartReservationViewSet, basename="part-reservation")
router.register("work-order-parts", WorkOrderPartViewSet, basename="work-order-part")
router.register("work-orders", WorkOrderViewSet, basename="work-order")
router.register("checklist-templates", ChecklistTemplateViewSet, basename="checklist-template")
router.register("inspections", InspectionViewSet, basename="inspection")
router.register("findings", FindingViewSet, basename="finding")
router.register("integration-events", IntegrationEventViewSet, basename="integration-event")
router.register("webhooks", WebhookEndpointViewSet, basename="webhook")

api_v1 = [
    path("auth/", include("apps.accounts.api_urls")),
    path("organization/", OrganizationViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
         name="organization"),
    path("platform/organizations/", PlatformOrganizationViewSet.as_view({"get": "list", "post": "create"}),
         name="platform-organizations-list"),
    path("platform/organizations/<uuid:pk>/", PlatformOrganizationViewSet.as_view({"get": "retrieve", "delete": "destroy"}),
         name="platform-organizations-detail"),
    path("platform/organizations/<uuid:pk>/status/", PlatformOrganizationViewSet.as_view({"post": "set_status"}),
         name="platform-organizations-status"),
    path("platform/organizations/<uuid:pk>/users/", PlatformOrganizationViewSet.as_view({"post": "create_user"}),
         name="platform-organizations-users"),
    path("platform/users/", PlatformUserViewSet.as_view({"post": "create"}),
         name="platform-users-create"),
    path("portal/", include("apps.portal.api_urls")),
    path("", include(router.urls)),
    path("", include("apps.workspace.api_urls")),
    path("", include("apps.dashboards.api_urls")),
    path("sla-metrics/", SLAMetricsView.as_view(), name="sla-metrics"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]


from django.views import View
from django.shortcuts import redirect

class AdminLandingRedirectView(View):
    """Graceful landing for /admin/ preventing dead-ends or login loops."""
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/accounts/login/?next={request.path}")
        if getattr(request.user, "is_platform_admin", False) or getattr(request.user, "is_superuser", False):
            return redirect("platform_admin:organizations")
        return redirect("ui:home")

urlpatterns = [
    path("admin/", AdminLandingRedirectView.as_view(), name="admin_landing"),
    path("admin", RedirectView.as_view(url="/admin/", permanent=False)),
    path("docs/", RedirectView.as_view(url="/api/v1/docs/", permanent=False)),
    path("swagger/", RedirectView.as_view(url="/api/v1/docs/", permanent=False)),
    path("assets/dashboard/", RedirectView.as_view(url="/app/", permanent=False)),
    path("planner/dashboard/", RedirectView.as_view(url="/app/", permanent=False)),
    path("inventory/dashboard/", RedirectView.as_view(url="/app/", permanent=False)),
    path("service-manager/dashboard/", RedirectView.as_view(url="/app/", permanent=False)),
    path("audit/view/", RedirectView.as_view(url="/app/audit/", permanent=False)),
    path("technician/dashboard/", RedirectView.as_view(url="/app/workspace/", permanent=False)),
    path("dispatcher/dashboard/", RedirectView.as_view(url="/app/", permanent=False)),
    path("supervisor/dashboard/", RedirectView.as_view(url="/app/", permanent=False)),
    path("portal/view/", RedirectView.as_view(url="/app/portal/", permanent=False)),
    path("health/live/", health.live, name="health_live"),
    path("health/ready/", health.ready, name="health_ready"),
    path("health/db/", health.database_status, name="health_db"),
    path("health/workers/", health.workers, name="health_workers"),
    path("health/email/", health.email_status, name="health_email"),
    path("platform/", include("apps.tenancy.platform_urls")),
    path("api/v1/", include(api_v1)),
    path("accounts/", include("apps.accounts.urls")),
    path("app/portal/", include("apps.portal.urls")),
    path("app/", include("apps.tenancy.urls")),
    path("app/", include("apps.rbac.urls")),
    path("app/", include("apps.audit.urls")),
    path("app/", include("apps.notifications.urls")),
    path("app/", include("apps.files.urls")),
    path("app/", include("apps.sites.urls")),
    path("app/", include("apps.assets.urls")),
    path("app/", include("apps.identification.urls")),
    path("app/", include("apps.incidents.urls")),
    path("app/", include("apps.inventory.urls")),
    path("app/", include("apps.workorders.urls_ui")),
    path("app/", include("apps.maintenance.urls")),
    path("app/", include("apps.sla.urls")),
    path("app/", include("apps.contracts.urls")),
    path("app/", include("apps.checklists.urls")),
    path("app/", include("apps.workspace.urls")),
    path("app/", include("apps.dashboards.urls")),
    # Module teams: add path("app/", include("apps.<module>.urls")) for your module here.
    path("", include("apps.ui.urls")),
]

from apps.files.views import protected_media_serve
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", protected_media_serve),
]

handler400 = "apps.ui.views.bad_request"
handler403 = "apps.ui.views.forbidden"
handler404 = "apps.ui.views.not_found"
handler500 = "apps.ui.views.server_error"

