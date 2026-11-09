import time
from playwright.sync_api import sync_playwright

urls = [
    ("Asset Management", "http://localhost:8000/product/asset-management/"),
    ("Service Management", "http://localhost:8000/product/service-management/"),
    ("Work Order Management", "http://localhost:8000/product/work-order-management/"),
    ("Inventory Management", "http://localhost:8000/product/inventory-management/"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for name, url in urls:
        resp = page.goto(url, wait_until="domcontentloaded")
        print(f"[{resp.status}] {name} -> {url} (Title: {page.title()})")

    browser.close()

