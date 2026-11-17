from django.urls import re_path

from . import api

urlpatterns = [
    re_path(r"^token/?$", api.TokenObtain.as_view(), name="token"),
    re_path(r"^token/refresh/?$", api.TokenRefresh.as_view(), name="token_refresh"),
    re_path(r"^logout/?$", api.LogoutView.as_view(), name="logout"),
    re_path(r"^me/?$", api.MeView.as_view(), name="me"),
]

