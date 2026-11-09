import os
import time
from playwright.sync_api import sync_playwright

def run():
    out_dir = r"C:\Users\veere\new internal\FieldOps_Nexus_Internal\scratch"
    os.makedirs(out_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("Navigating to http://localhost:8000/ ...")
        page.goto("http://localhost:8000/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.5)

        # 1. PRODUCT DROPDOWN HOVER
        print("Testing Product hover...")
        prod_btn = page.locator('button[data-fx-mega-trigger="product"]')
        prod_btn.hover()
        time.sleep(0.5)
        assert page.locator('#mega-product').is_visible(), "Product mega menu not visible on hover!"
        print("Product dropdown visible on hover.")

        # 2. SOLUTIONS DROPDOWN HOVER
        print("Testing Solutions hover...")
        sol_btn = page.locator('button[data-fx-mega-trigger="solutions"]')
        sol_btn.hover()
        time.sleep(0.5)
        assert page.locator('#mega-solutions').is_visible(), "Solutions mega menu not visible on hover!"
        assert not page.locator('#mega-product').is_visible(), "Product mega menu did not close when Solutions opened!"
        print("Solutions dropdown visible on hover; Product closed.")

        # 3. MODULES DROPDOWN HOVER
        print("Testing Modules hover...")
        mod_btn = page.locator('button[data-fx-mega-trigger="modules"]')
        mod_btn.hover()
        time.sleep(0.5)
        assert page.locator('#mega-modules').is_visible(), "Modules mega menu not visible on hover!"
        assert not page.locator('#mega-solutions').is_visible(), "Solutions mega menu did not close when Modules opened!"
        print("Modules dropdown visible on hover; Solutions closed.")

        # 4. TEST ESCAPE KEY
        print("Testing Escape key...")
        page.keyboard.press("Escape")
        time.sleep(0.4)
        active_panels = page.locator('.fx-mega-menu.is-active').count()
        print(f"Active mega menus after Escape: {active_panels} (Expected: 0)")
        assert active_panels == 0, "Escape did not close mega menu!"

        # 5. TEST CLICK TO OPEN & OUTSIDE CLICK
        print("Testing Click to Open on closed state...")
        page.mouse.move(10, 10)
        time.sleep(0.3)
        prod_btn.dispatch_event('click')
        time.sleep(0.5)
        assert page.locator('#mega-product').is_visible(), "Click did not open Product mega menu!"
        print("Product opened via click.")

        print("Testing Outside Click to close...")
        page.mouse.click(100, 500)
        time.sleep(0.5)
        active_panels = page.locator('.fx-mega-menu.is-active').count()
        print(f"Active mega menus after outside click: {active_panels} (Expected: 0)")
        assert active_panels == 0, "Outside click did not close mega menu!"

        # 6. MOBILE TESTING
        print("\nTesting Mobile Viewport (430x932)...")
        mobile_context = browser.new_context(viewport={"width": 430, "height": 932})
        m_page = mobile_context.new_page()
        m_page.goto("http://localhost:8000/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(1)

        # Click hamburger
        m_toggle = m_page.locator('[data-fx-pub-toggle]')
        m_toggle.click()
        time.sleep(0.5)

        # Check Product Accordion
        m_prod = m_page.locator('button[data-fx-mobile-accordion="m-acc-product"]')
        m_prod.click()
        time.sleep(0.5)
        prod_acc_links = m_page.locator('#m-acc-product a.fx-mobile-sublink').count()
        print(f"Mobile Product accordion links: {prod_acc_links} (Expected: 4)")
        assert prod_acc_links == 4, f"Expected 4 links, got {prod_acc_links}"

        # Check Solutions Accordion
        m_sol = m_page.locator('button[data-fx-mobile-accordion="m-acc-solutions"]')
        m_sol.click()
        time.sleep(0.5)
        sol_acc_links = m_page.locator('#m-acc-solutions a.fx-mobile-sublink').count()
        print(f"Mobile Solutions accordion links: {sol_acc_links} (Expected: 4)")
        assert sol_acc_links == 4, f"Expected 4 links, got {sol_acc_links}"

        # Check Modules Accordion
        m_mod = m_page.locator('button[data-fx-mobile-accordion="m-acc-modules"]')
        m_mod.click()
        time.sleep(0.5)
        mod_acc_links = m_page.locator('#m-acc-modules a.fx-mobile-sublink').count()
        print(f"Mobile Modules accordion links: {mod_acc_links} (Expected: 4)")
        assert mod_acc_links == 4, f"Expected 4 links, got {mod_acc_links}"

        m_ss = os.path.join(out_dir, "screenshot_mobile_accordion.png")
        m_page.screenshot(path=m_ss)
        print(f"Captured Mobile accordion: {m_ss}")

        # 7. TEST LINK NAVIGATION
        print("\nTesting Link Navigation for Product Item 1 (Asset Management)...")
        # Hover product again
        prod_btn.hover()
        time.sleep(0.4)
        with page.expect_navigation():
            page.locator('#mega-product a.fx-mega-card').first.click()
        print(f"Navigated to: {page.url} (Expected: http://localhost:8000/product/asset-management/)")
        assert "/product/asset-management/" in page.url, "Navigation failed!"

        browser.close()
        print("\n=======================================================")
        print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY WITH 100% PASS!")
        print("=======================================================")

if __name__ == "__main__":
    run()
