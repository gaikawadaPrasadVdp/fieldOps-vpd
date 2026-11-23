# Performance Test Triage — Localhost campaign 2026-11-20

**Source:** `FieldOps_Performance_Test_Report_20261120_1106.xlsx` (538 cases, 84 FAIL, 77 confirmed
"application failures" on re-run). SLAs are QA-assumed (p95 ≤ 500 ms list/detail, ≤ 1500 ms heavy),
not from the PRD/code. Environment: a single Windows host running k6 + Docker + Postgres together —
"relative behaviour, not production capacity" (tester's own caveat).

## The failures split into three tiers

### Tier 1 — Pathological (seconds-level p95): real query bugs
| Endpoint | p95 | Root cause |
|---|---|---|
| `/api/v1/sites/` | 22.2 s | **FIXED.** `sites/selectors.py::with_site_counts` used two JOIN-based `Count()` (zones + assets) in one queryset → a sites×zones×assets cartesian product. Replaced with independent correlated subqueries. Also fixes `/sites/{id}/` (8.5 s, same path). |
| `/api/v1/service-requests/` `/requests/` `/incidents/` | 6.5 s | N+1: `incidents/api_views.py::ServiceRequestSerializer.get_work_orders` runs a fresh `WorkOrder.objects.filter(source_reference=obj.number...)` **per row** (ignores the `prefetch_related("work_orders")` already on the queryset, because it links by `source_reference` string, not the FK). |
| `/api/v1/portal/requests` | 5.0 s | N+1: `portal/api_views.py::PortalServiceRequestSerializer.get_attachments_count` runs `evidence_for(...).count()` per row (generic-relation count). |
| `/api/v1/warranties/` `/agreements/` `/contracts/` `/coverage-agreements/` | 2.1–4.7 s | N+1 in `contracts/api_views.py::AgreementSerializer`: `get_assets` and `get_excluded_work_types` query per row. |
| `/api/v1/work-orders/` `/workorders/` | 8–10 s | Heavy list serializer + volume (810 WOs); check `WorkOrderSerializer.get_checklist` for per-row work. |
| `/api/v1/audit-logs/export/` | 10 s | Export endpoint (HEAVY tier). Inherently heavy; needs streamed/paginated export, not an N+1 fix. |

**Recommended fixes (behaviour-preserving; verify with `tests/test_query_performance_regression.py`
and `tests/test_performance_optimizations.py`, then the k6 rig):** batch/prefetch the per-row work
orders (custom `Prefetch` keyed on `number`/`source_reference`), annotate `attachments_count` and the
agreement asset lists via subqueries, and stream the audit export. These touch serializer output, so
they need the query-count tests run — not done blind here.

### Tier 2 — Marginal (p95 ~500–800 ms): environmental, not code defects
~50 list/detail endpoints land just over the **assumed** 500 ms line at 50 VU on a single host that is
simultaneously running the load generator, Docker VM and database. These are a function of the test
rig and the self-imposed SLA, not application defects. They should be re-measured on a representative
host (separate load generator, no DEBUG, nginx caching) before being treated as regressions.

### Tier 3 — Did not reproduce alone (108 incl. SPK-001) / STOPPED-CAPACITY (2)
Already excluded by the tester or are capacity-ceiling observations, not defects.

## Status — fixes applied (verify with query-count tests + k6 before trusting latency numbers)
- **Sites** — `src/apps/sites/selectors.py::with_site_counts`: cartesian JOIN Count → correlated subqueries.
- **Service requests** — `incidents/api_views.py::ServiceRequestSerializer`: `get_work_orders` now
  batches all page rows into one query via a cached map (identical output).
- **Portal requests** — `portal/api_views.py`: `attachments_count` annotated with one correlated
  subquery; the per-row `.count()` is now a fallback only.
- **Agreements/warranties/contracts** — `contracts/api_views.py`: list prefetches `exclusions` and
  `covered_assets__asset`; `get_assets`/`get_excluded_work_types` use the prefetch.
- **Indexes (Tier 2)** — added `(organization, -created_at)` to ServiceRequest, WorkOrder,
  CoverageAgreement and Site for the "filter by org, order by created_at, paginate" path.
  **Requires `python manage.py makemigrations && migrate`** (not generated here — no Django/DB in this workspace).
- **Still open (behaviour-sensitive, deferred):** Work Orders list (`get_checklist` → per-row
  `get_checklist_status` queries Inspection/ChecklistTemplate for checklist-required WOs — needs a
  batched inspection prefetch + cached org-level template check) and the audit-logs export (needs a
  streamed/paginated export, not an N+1 fix).
- **Pagination:** already capped (`StandardPagination.max_page_size=200`); no change.
- **Environmental:** Tier 2 marginal 500–800 ms — re-measure on a representative rig.

## Verification (user runs)
```
python manage.py makemigrations && python manage.py migrate   # for the new indexes
pytest tests/test_query_performance_regression.py tests/test_performance_optimizations.py \
       tests/test_sites.py tests/test_incidents.py tests/test_contracts_export.py \
       tests/test_portal_request_tracking.py -q
```
Then re-run the k6 sites / service-requests / portal / agreements sweeps.
