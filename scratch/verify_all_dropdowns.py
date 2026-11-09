import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8000/", wait_until="domcontentloaded", timeout=15000)
    time.sleep(1.0)

    # Hover Solutions
    page.locator('button[data-fx-mega-trigger="solutions"]').hover()
    time.sleep(0.5)
    page.screenshot(path=r"C:\Users\veere\new internal\FieldOps_Nexus_Internal\scratch\verify_solutions_unaffected.png")

    # Hover Modules
    page.locator('button[data-fx-mega-trigger="modules"]').hover()
    time.sleep(0.5)
    page.screenshot(path=r"C:\Users\veere\new internal\FieldOps_Nexus_Internal\scratch\verify_modules_unaffected.png")

    browser.close()
    print("Verification screenshots saved.")

