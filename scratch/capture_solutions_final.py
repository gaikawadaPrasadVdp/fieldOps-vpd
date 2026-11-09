import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8000/", wait_until="domcontentloaded", timeout=15000)
    time.sleep(1.5)

    btn = page.locator('button[data-fx-mega-trigger="solutions"]')
    btn.hover()
    time.sleep(0.8)

    page.screenshot(path=r"C:\Users\veere\new internal\FieldOps_Nexus_Internal\scratch\solutions_dropdown_verified_final.png")
    browser.close()
    print("Screenshot successfully saved.")

