from apps.ui.navigation import NavItem, register

register(
    NavItem(
        "My Jobs",
        "workspace:my_jobs",
        "work_order.view_assigned",
        "wrench",
        "Operations",
        25,
        "/app/workspace",
    )
)
register(
    NavItem(
        "Technicians & Shifts",
        "workspace:technician_list",
        "user.view",
        "users",
        "Operations",
        26,
        "/app/workspace/technicians",
    )
)
