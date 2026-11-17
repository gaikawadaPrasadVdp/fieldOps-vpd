from django.urls import path
from . import views

app_name = "portal"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("requests/", views.RequestListView.as_view(), name="requests_list"),
    path("requests/new/", views.RequestCreateView.as_view(), name="request_create"),
    path("requests/<str:pk>/", views.RequestDetailView.as_view(), name="request_detail"),
    path("requests/<str:pk>/confirm/", views.RequestConfirmView.as_view(), name="request_confirm"),
    path("requests/<str:pk>/reopen/", views.RequestReopenView.as_view(), name="request_reopen"),
    path("requests/<str:pk>/comments/", views.PortalCommentCreateView.as_view(), name="request_comments"),
    path("scan/", views.PortalScanView.as_view(), name="scan"),
    path("s/<str:token>/report/", views.PortalScanReportView.as_view(), name="scan_report"),
    path("s/<str:token>/", views.PortalScanResolveView.as_view(), name="scan_resolve"),
    path("accounts/", views.AccountsListView.as_view(), name="accounts_list"),
    path("accounts/<str:pk>/edit/", views.AccountEditView.as_view(), name="account_edit"),
    path("accounts/<str:pk>/toggle/", views.AccountToggleView.as_view(), name="account_toggle"),
]
