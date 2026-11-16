from apps.rbac.catalog import register

register(
    "dashboards",
    "report.view",
    "View operational dashboards and KPI reports",
    site_scoped=True,
)

register(
    "dashboards",
    "report.manage",
    "Generate and manage report snapshots",
    site_scoped=True,
)
