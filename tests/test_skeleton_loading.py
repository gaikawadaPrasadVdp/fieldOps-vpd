"""Tests verifying Skeleton Loading system and components."""
from django.template.loader import render_to_string


def test_skeleton_card_template_renders():
    """Verify reusable skeleton card template renders with proper shimmer classes."""
    rendered = render_to_string("components/_skeleton_card.html")
    assert "fx-skeleton-card" in rendered
    assert "fx-skeleton fx-skeleton-badge" in rendered
    assert "fx-skeleton fx-skeleton-title" in rendered
    assert "fx-skeleton fx-skeleton-text" in rendered
    assert "aria-hidden=\"true\"" in rendered


def test_skeleton_table_template_renders():
    """Verify reusable skeleton table template renders with rows."""
    rendered = render_to_string("components/_skeleton_table.html")
    assert "fx-skeleton-table-row-container" in rendered
    assert "fx-skeleton fx-skeleton-badge" in rendered
    assert "fx-skeleton fx-skeleton-btn" in rendered
    assert "aria-hidden=\"true\"" in rendered


def test_workspace_jobs_template_includes_skeleton_indicator():
    """Verify workspace my_jobs template includes the skeleton container for HTMX."""
    rendered = render_to_string(
        "workspace/my_jobs.html",
        {
            "capacity": None,
            "active_count": 0,
            "upcoming_count": 0,
            "completed_count": 0,
            "all_count": 0,
            "status_filter": "active",
            "search": "",
            "jobs_page": [],
        },
    )
    assert 'id="jobs-skeleton"' in rendered
    assert "fx-skeleton-container" in rendered
    assert "hx-indicator=\"#jobs-skeleton\"" in rendered
