import time
from playwright.sync_api import sync_playwright

urls = [
    ("Maintenance Management", "http://localhost:8000/modules/maintenance-management/"),
    ("Workforce Management", "http://localhost:8000/modules/workforce-management/"),
    ("Analytics & Reporting", "http://localhost:8000/modules/analytics-reporting/"),
    ("Audit & Traceability", "http://localhost:8000/modules/audit-traceability/"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for name, url in urls:
        resp = page.goto(url, wait_until="domcontentloaded")
        print(f"[{resp.status}] {name} -> {url} (Title: {page.title()})")

    browser.close()

