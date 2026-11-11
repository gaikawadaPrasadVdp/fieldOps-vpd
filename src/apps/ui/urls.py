from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "ui"
urlpatterns = [
    path("", views.root, name="root"),
    path("product/", views.public_product_overview, name="public_product_overview"),
    path("product/<slug:slug>/", views.public_product, name="public_product"),
    path("features/", views.public_features, name="public_features"),
    path("solutions/", views.public_solutions, name="public_solutions"),
    path("solutions/<slug:slug>/", views.public_solution, name="public_solution"),
    path("platform/", views.public_modules, name="public_platform_overview"),
    path("platform/<str:module_id>/", views.public_module, name="public_platform"),
    path(
        "modules/",
        RedirectView.as_view(
            pattern_name="ui:public_platform_overview",
            permanent=True,
            query_string=True,
        ),
        name="public_modules",
    ),
    path(
        "modules/<str:module_id>/",
        RedirectView.as_view(
            pattern_name="ui:public_platform",
            permanent=True,
            query_string=True,
        ),
        name="public_module",
    ),
    path("resources/", views.public_resources, name="public_resources"),
    path("about/", views.public_about, name="public_about"),
    path("contact-sales/", views.public_contact_sales, name="public_contact_sales"),
    path(
        "contact/",
        RedirectView.as_view(
            pattern_name="ui:public_contact_sales",
            permanent=True,
            query_string=True,
        ),
        name="public_contact",
    ),
    path("sitemap/", views.public_sitemap, name="public_sitemap"),
    path("register/", views.client_register, name="client_register"),
    path("client-register/", views.client_register, name="client_register_alias"),
    path("legal/privacy-policy/", views.public_privacy_policy, name="public_privacy_policy"),
    path("legal/terms-of-service/", views.public_terms_of_service, name="public_terms_of_service"),
    path("legal/terms-and-conditions/", views.public_terms_of_service, name="public_terms_and_conditions"),
    path("legal/disclaimer/", views.public_disclaimer, name="public_disclaimer"),
    path("legal/cookie-policy/", views.public_cookie_policy, name="public_cookie_policy"),
    path("legal/<slug:slug>/", views.public_legal, name="public_legal"),
    path("app/", views.home, name="home"),
    path("app/choose-organization/", views.choose_org, name="choose_org"),
    path("app/switch-organization/", views.switch_org, name="switch_org"),
    path("app/search/", views.search, name="search"),
]
