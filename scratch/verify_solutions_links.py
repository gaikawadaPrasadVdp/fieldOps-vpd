import time
from playwright.sync_api import sync_playwright

urls = [
    ("Enterprise Operations", "http://localhost:8000/solutions/enterprise-operations/"),
    ("SLA Management", "http://localhost:8000/solutions/sla-management/"),
    ("Multi-Site Management", "http://localhost:8000/solutions/multi-site-management/"),
    ("Connected Data", "http://localhost:8000/solutions/connected-data/"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for name, url in urls:
        resp = page.goto(url, wait_until="domcontentloaded")
        print(f"[{resp.status}] {name} -> {url} (Title: {page.title()})")

    browser.close()

