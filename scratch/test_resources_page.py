import time
from playwright.sync_api import sync_playwright

def inspect_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto("http://localhost:8000/resources/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.5)

        # Take screenshot of page
        page.screenshot(path=r"FieldOps_Nexus_Internal\scratch\resources_initial.png")

        # Check expand buttons
        expand_btns = page.locator(".fx-card-expand-btn")
        print(f"Expand buttons count: {expand_btns.count()}")

        # Check Read Article buttons
        read_btns = page.locator(".fx-read-more-link")
        print(f"Read Article buttons count: {read_btns.count()}")

        # Click first Read Article button
        read_btns.first.click()
        time.sleep(1)

        modal = page.locator("#fx-article-modal-overlay")
        is_visible = modal.is_visible()
        print(f"Modal is visible after click: {is_visible}")

        page.screenshot(path=r"FieldOps_Nexus_Internal\scratch\resources_modal_test.png")

        browser.close()

if __name__ == "__main__":
    inspect_page()

