import os
import time
from playwright.sync_api import sync_playwright

def verify():
    out_dir = r"C:\Users\veere\new internal\FieldOps_Nexus_Internal\scratch"
    os.makedirs(out_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("Navigating to http://localhost:8000/ ...")
        page.goto("http://localhost:8000/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)

        # 1. HOVER ON PRODUCT
        print("Hovering on Product nav trigger...")
        prod_btn = page.locator('button[data-fx-mega-trigger="product"]')
        prod_btn.hover()
        time.sleep(0.6)

        # Check that Product mega menu is visible
        mega_prod = page.locator('#mega-product')
        assert mega_prod.is_visible(), "Product mega menu is not visible on hover!"
        print("Product mega menu is visible.")

        # Check the 4 cards
        cards = page.locator('#mega-product .fx-mega-card')
        count = cards.count()
        print(f"Total cards in Product dropdown: {count} (Expected: 4)")
        assert count == 4, f"Expected 4 cards, got {count}"

        card_titles = [cards.nth(i).locator('.fx-mega-card-title').inner_text().strip() for i in range(count)]
        print("Card titles:", card_titles)

        expected_titles = [
            "Asset Management",
            "Service Management",
            "Work Order Management",
            "Inventory Management"
        ]
        assert card_titles == expected_titles, f"Titles mismatch! Expected {expected_titles}, got {card_titles}"

        # Hover first card (Asset Management) to capture active/hover state with gold highlight
        cards.first.hover()
        time.sleep(0.5)

        desktop_ss = os.path.join(out_dir, "product_dropdown_verified.png")
        page.screenshot(path=desktop_ss)
        print(f"Captured desktop screenshot: {desktop_ss}")

        # 2. MOBILE VIEW
        print("\nTesting mobile view (430x932)...")
        m_context = browser.new_context(viewport={"width": 430, "height": 932})
        m_page = m_context.new_page()
        m_page.goto("http://localhost:8000/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(1)

        # Open mobile drawer
        m_page.locator('[data-fx-pub-toggle]').click()
        time.sleep(0.5)

        # Open Product accordion
        m_prod_acc = m_page.locator('button[data-fx-mobile-accordion="m-acc-product"]')
        m_prod_acc.click()
        time.sleep(0.5)

        m_links = m_page.locator('#m-acc-product a.fx-mobile-sublink')
        m_count = m_links.count()
        print(f"Total mobile Product links: {m_count} (Expected: 4)")
        assert m_count == 4, f"Expected 4 mobile links, got {m_count}"

        m_titles = [m_links.nth(i).inner_text().strip() for i in range(m_count)]
        print("Mobile link titles:", m_titles)

        mobile_ss = os.path.join(out_dir, "product_mobile_verified.png")
        m_page.screenshot(path=mobile_ss)
        print(f"Captured mobile screenshot: {mobile_ss}")

        browser.close()
        print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    verify()

