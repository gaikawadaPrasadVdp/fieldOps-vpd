import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1200})
    page.goto("http://localhost:8000/resources/", wait_until="domcontentloaded", timeout=15000)
    time.sleep(1.0)

    grid = page.locator("#resources-grid")
    grid.scroll_into_view_if_needed()
    time.sleep(0.5)

    page.screenshot(path=r"FieldOps_Nexus_Internal\scratch\resources_catalog_grid.png")
    browser.close()

