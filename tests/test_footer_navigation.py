import pytest
from django.test import RequestFactory
from django.urls import resolve, reverse

from apps.ui import views


def test_footer_urls_reverse_and_resolve():
    """Verify that all dedicated routes reverse to correct URLs and resolve to distinct views."""
    url_view_map = [
        ("ui:public_contact_sales", "/contact-sales/", views.public_contact_sales),
        ("ui:public_privacy_policy", "/legal/privacy-policy/", views.public_privacy_policy),
        ("ui:public_terms_of_service", "/legal/terms-of-service/", views.public_terms_of_service),
        ("ui:public_disclaimer", "/legal/disclaimer/", views.public_disclaimer),
        ("ui:public_cookie_policy", "/legal/cookie-policy/", views.public_cookie_policy),
    ]

    for url_name, expected_path, expected_view in url_view_map:
        reversed_url = reverse(url_name)
        assert reversed_url == expected_path, f"URL {url_name} reversed to {reversed_url}, expected {expected_path}"
        match = resolve(expected_path)
        assert match.func == expected_view, f"Path {expected_path} resolved to {match.func}, expected {expected_view}"


def test_backward_compatible_aliases():
    """Verify legacy URL patterns resolve properly without breaking older links."""
    assert resolve("/contact/").url_name == "public_contact"
    assert resolve("/legal/terms-and-conditions/").func == views.public_terms_of_service


def test_careers_completely_removed():
    """Verify careers URL cannot be resolved or reversed, and is not in navigation."""
    from django.urls.exceptions import Resolver404, NoReverseMatch
    from django.template.loader import render_to_string

    with pytest.raises(Resolver404):
        resolve("/careers/")

    with pytest.raises(NoReverseMatch):
        reverse("ui:public_careers")

    rendered = render_to_string("public/base_public.html", {"active_page": "home"})
    assert "careers" not in rendered.lower()


def test_sitemap_resolves_and_renders():
    """Verify sitemap URL resolves to public_sitemap and renders successfully."""
    match = resolve("/sitemap/")
    assert match.func == views.public_sitemap
    rf = RequestFactory()
    req = rf.get("/sitemap/")
    resp = views.public_sitemap(req)
    assert resp.status_code == 200


def test_each_page_renders_unique_dedicated_content():
    """Verify each page renders its own unique title, content, and headings."""
    rf = RequestFactory()

    pages = {
        "contact_sales": {
            "req": rf.get("/contact-sales/"),
            "view": views.public_contact_sales,
            "must_contain": [
                "Let&rsquo;s Start a",
                "Conversation",
                "support@fieldopsnexus.com",
                "Business Conversations That Matter",
            ],
            "must_not_contain": [
                "Cookie &amp; Session Management Policy",
                "Open Positions",
                "General Information &amp; Decision-Support Disclaimer",
            ],
        },
        "privacy_policy": {
            "req": rf.get("/legal/privacy-policy/"),
            "view": views.public_privacy_policy,
            "must_contain": [
                "Privacy Policy &amp; Data Protection",
                "Information Collection and Usage",
                "Data Protection and Security",
                "Data Retention and Decommissioning",
                "User Privacy Rights &amp; Regulatory Compliance",
                "privacy@fieldopsnexus.com",
            ],
            "must_not_contain": [
                "Open Positions",
                "Enterprise Sales Inquiry",
            ],
        },
        "terms_of_service": {
            "req": rf.get("/legal/terms-of-service/"),
            "view": views.public_terms_of_service,
            "must_contain": [
                "Terms of Service &amp; Agreement",
                "Acceptance of Terms &amp; Governance",
                "Platform Usage Conditions &amp; Licensing",
                "User Responsibilities &amp; Acceptable Use",
                "Account and Access Policies",
                "Limitations of Liability",
            ],
            "must_not_contain": [
                "What Cookies Are",
                "Senior Systems Architect",
            ],
        },
        "disclaimer": {
            "req": rf.get("/legal/disclaimer/"),
            "view": views.public_disclaimer,
            "must_contain": [
                "Enterprise System Disclaimer",
                "General Information &amp; Decision-Support Disclaimer",
                "Platform Availability &amp; Maintenance Windows",
                "Accuracy of Information &amp; Field Telemetry",
                "Third-Party Services &amp; Integrations",
                "90-calendar-day evaluation gate",
            ],
            "must_not_contain": [
                "Open Positions",
                "What Cookies Are",
            ],
        },
        "cookie_policy": {
            "req": rf.get("/legal/cookie-policy/"),
            "view": views.public_cookie_policy,
            "must_contain": [
                "Cookie &amp; Session Policy",
                "What Cookies Are",
                "Types of Cookies Used on FieldOps Nexus",
                "sessionid",
                "csrftoken",
                "Cookie Preferences &amp; Browser Management",
            ],
            "must_not_contain": [
                "Senior Systems Architect",
                "Enterprise Sales Inquiry",
            ],
        },
    }

    rendered_contents = {}
    for key, spec in pages.items():
        resp = spec["view"](spec["req"])
        assert resp.status_code == 200, f"Page {key} returned status {resp.status_code}"
        content = resp.content.decode("utf-8")
        rendered_contents[key] = content

        for item in spec["must_contain"]:
            assert item in content, f"Page {key} missing expected content: '{item}'"

        for item in spec["must_not_contain"]:
            assert item not in content, f"Page {key} improperly contained content from other pages: '{item}'"

    # Verify no two pages have identical content
    page_keys = list(rendered_contents.keys())
    for i in range(len(page_keys)):
        for j in range(i + 1, len(page_keys)):
            k1, k2 = page_keys[i], page_keys[j]
            assert rendered_contents[k1] != rendered_contents[k2], f"Pages {k1} and {k2} have identical content!"


def test_footer_contains_all_dedicated_links():
    """Verify base_public footer includes dedicated links with correct paths."""
    from django.template.loader import render_to_string
    rendered_footer = render_to_string("public/base_public.html", {"active_page": "home"})

    expected_links = [
        'href="/contact-sales/"',
        'href="/legal/privacy-policy/"',
        'href="/legal/terms-of-service/"',
        'href="/legal/disclaimer/"',
        'href="/legal/cookie-policy/"',
    ]

    for link in expected_links:
        assert link in rendered_footer, f"Footer missing expected link: {link}"

    # Careers must NOT be in footer
    assert 'href="/careers/"' not in rendered_footer
    assert "careers" not in rendered_footer.lower()

