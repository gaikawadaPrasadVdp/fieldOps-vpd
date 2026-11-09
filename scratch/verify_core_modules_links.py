import time
from playwright.sync_api import sync_playwright

def test_core_modules_links():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.goto("http://localhost:8000/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.5)

        cards = page.locator("#modules .module-card")
        count = cards.count()
        print(f"Total cards found in #modules: {count}")

        card_data = []
        for i in range(count):
            card = cards.nth(i)
            title = card.locator(".module-card-title").text_content().strip()
            href = card.get_attribute("href")
            card_data.append((title, href))
            print(f"Card {i+1}: '{title}' -> href='{href}'")

        # Now test clicking each of the four cards
        target_cards = [
            ("Asset Management", "/product/asset-management/"),
            ("Service Management", "/product/service-management/"),
            ("Work Order Management", "/product/work-order-management/"),
            ("Inventory Management", "/product/inventory-management/"),
        ]

        print("\n--- Testing Card Navigation ---")
        for title, expected_path in target_cards:
            page.goto("http://localhost:8000/", wait_until="domcontentloaded", timeout=15000)
            time.sleep(1.0)

            # Find the specific card
            card = page.locator(f"#modules .module-card:has-text('{title}')")
            card.scroll_into_view_if_needed()
            time.sleep(0.5)

            # Click card
            with page.expect_navigation():
                card.click()

            current_url = page.url
            page_title = page.title()
            print(f"Clicked '{title}': Navigated to '{current_url}', Page title: '{page_title}'")
            assert expected_path in current_url, f"Expected {expected_path} in {current_url}"

        print("\nAll 4 target cards successfully navigate to their Product detail pages!")
        browser.close()

if __name__ == "__main__":
    test_core_modules_links()
