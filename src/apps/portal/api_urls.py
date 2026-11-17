from django.urls import path
from .api_views import (
    PortalAccountViewSet,
    PortalAssetListView,
    PortalMeView,
    PortalRequestConfirmView,
    PortalRequestDetailView,
    PortalRequestListCreateView,
    PortalRequestReopenView,
)

app_name = "portal_api"

account_list = PortalAccountViewSet.as_view({"get": "list", "post": "create"})
account_detail = PortalAccountViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"})
account_toggle = PortalAccountViewSet.as_view({"post": "toggle"})

urlpatterns = [
    path("me/", PortalMeView.as_view(), name="me"),
    path("assets/", PortalAssetListView.as_view(), name="assets"),
    path("assets", PortalAssetListView.as_view()),
    path("requests/", PortalRequestListCreateView.as_view(), name="requests"),
    path("requests", PortalRequestListCreateView.as_view()),
    path("requests/<str:pk>/confirm/", PortalRequestConfirmView.as_view(), name="request_confirm"),
    path("requests/<str:pk>/confirm", PortalRequestConfirmView.as_view()),
    path("requests/<str:pk>/reopen/", PortalRequestReopenView.as_view(), name="request_reopen"),
    path("requests/<str:pk>/reopen", PortalRequestReopenView.as_view()),
    path("requests/<str:pk>/", PortalRequestDetailView.as_view(), name="request_detail"),
    path("requests/<str:pk>", PortalRequestDetailView.as_view()),
    # Alias routes for QA/client expectations at /api/v1/portal/accounts/
    path("accounts/", account_list, name="accounts_list_alias"),
    path("accounts", account_list),
    path("accounts/<str:pk>/", account_detail, name="account_detail_alias"),
    path("accounts/<str:pk>", account_detail),
    path("accounts/<str:pk>/toggle/", account_toggle, name="account_toggle_alias"),
    path("accounts/<str:pk>/toggle", account_toggle),
]



