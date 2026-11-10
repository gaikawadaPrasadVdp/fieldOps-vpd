"""Unified pagination utilities for FieldOps Nexus dashboards and multi-table views."""
from __future__ import annotations

from urllib.parse import urlencode
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage


def paginate_dashboard_queryset(request, queryset, page_param: str = "page", per_page: int = 10):
    """Safely paginate any dashboard queryset or list.

    - Clamps invalid or negative page numbers to page 1.
    - Clamps page numbers beyond the max page to paginator.num_pages.
    - Generates a preserved query string omitting ``page_param`` so existing filters are kept in page links.
    """
    paginator = Paginator(queryset, per_page)
    raw_page = request.GET.get(page_param, "1")

    try:
        page_num = int(raw_page)
        if page_num < 1:
            page_num = 1
    except (ValueError, TypeError):
        page_num = 1

    if paginator.num_pages > 0 and page_num > paginator.num_pages:
        page_num = paginator.num_pages

    try:
        page_obj = paginator.page(page_num)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)

    # Build preserved query string without the current page parameter
    query_dict = request.GET.copy()
    if page_param in query_dict:
        query_dict.pop(page_param)
    preserved_params = query_dict.urlencode()

    return page_obj, preserved_params
