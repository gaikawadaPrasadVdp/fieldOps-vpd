import time
from playwright.sync_api import sync_playwright

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto("http://localhost:8000/resources/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.5)

        print("=== 1. VERIFYING FLOATING BUTTONS REMOVAL ===")
        expand_btns = page.locator(".fx-card-expand-btn")
        print(f"Floating expand buttons found: {expand_btns.count()}")
        assert expand_btns.count() == 0, "Error: Floating expand buttons still exist in DOM!"

        collapse_triggers = page.locator(".fx-collapse-trigger")
        print(f"Collapse triggers found: {collapse_triggers.count()}")
        assert collapse_triggers.count() == 0, "Error: Collapse triggers still exist in DOM!"

        # Scroll to catalog grid
        grid = page.locator("#resources-grid")
        grid.scroll_into_view_if_needed()
        time.sleep(0.5)

        # Capture Clean Grid Screenshot
        page.screenshot(path=r"FieldOps_Nexus_Internal\scratch\verified_clean_grid.png")
        print("Captured verified_clean_grid.png")

        print("\n=== 2. VERIFYING CATEGORY FILTERS ===")
        categories = [
            ("all", 6),
            ("product-guides", 1),
            ("documentation", 2),
            ("industry-insights", 1),
            ("operational-playbooks", 2),
        ]

        for cat_key, expected_count in categories:
            btn = page.locator(f".fx-filter-btn[data-filter='{cat_key}']")
            btn.click()
            time.sleep(0.4)

            # Check active class
            is_active = "active" in (btn.get_attribute("class") or "")
            aria_sel = btn.get_attribute("aria-selected") == "true"
            print(f"Filter [{cat_key}]: active={is_active}, aria-selected={aria_sel}")
            assert is_active and aria_sel, f"Filter {cat_key} is not marked active!"

            # Check visible cards
            visible_cards = page.locator(".fx-resource-card-col:visible")
            vis_count = visible_cards.count()
            print(f"Filter [{cat_key}]: {vis_count} visible cards (expected {expected_count})")
            assert vis_count == expected_count, f"Filter {cat_key} expected {expected_count} cards, got {vis_count}"

            # Check that every visible card belongs to this category (unless all)
            if cat_key != "all":
                for idx in range(vis_count):
                    card_cat = visible_cards.nth(idx).get_attribute("data-category")
                    assert card_cat == cat_key, f"Card category mismatch: expected {cat_key}, got {card_cat}"

        print("\n=== 3. VERIFYING MODAL OPENING & CONTENT ACROSS CATEGORIES ===")
        test_articles = [
            ("all", "Enterprise Asset Lifecycle & Preventive Maintenance Playbook", "OPERATIONAL PLAYBOOKS"),
            ("product-guides", "Optimization of Mobile Technician Dispatch & Route Scheduling", "PRODUCT GUIDES"),
            ("documentation", "FieldOps Nexus API & ERP Integration Architecture", "DOCUMENTATION"),
            ("industry-insights", "Continuous Audit Readiness: Eliminating Paper Compliance Gaps", "INDUSTRY INSIGHTS"),
            ("documentation", "Double-Entry Inventory Ledger for Spare Parts", "DOCUMENTATION"),
            ("operational-playbooks", "SLA Design for Complex Multi-Site Operations", "OPERATIONAL PLAYBOOKS"),
        ]

        overlay = page.locator("#fx-article-modal-overlay")
        modal = page.locator("#fx-article-modal")

        for cat_filter, expected_title, expected_cat_badge in test_articles:
            # Switch to category
            page.locator(f".fx-filter-btn[data-filter='{cat_filter}']").click()
            time.sleep(0.3)

            # Find card
            card = page.locator(f".fx-resource-card-col:visible:has-text('{expected_title}')")
            assert card.count() > 0, f"Card '{expected_title}' not found in category '{cat_filter}'"

            # Click Read Article button
            read_btn = card.locator(".fx-read-more-link")
            read_btn.click()
            time.sleep(0.5)

            # Verify modal is open
            assert overlay.is_visible(), f"Modal overlay not visible for '{expected_title}'"
            assert "is-open" in (overlay.get_attribute("class") or ""), "Modal lacks .is-open class"

            # Verify background scrolling is locked
            body_overflow = page.evaluate("() => document.body.style.overflow")
            assert body_overflow == "hidden", f"Body overflow expected 'hidden', got '{body_overflow}'"

            # Verify Modal Content
            modal_title = page.locator("#fx-modal-title").text_content().strip()
            modal_cat = page.locator("#fx-modal-category-text").text_content().strip()
            modal_date = page.locator("#fx-modal-date").text_content().strip()
            modal_readtime = page.locator("#fx-modal-readtime").text_content().strip()
            modal_desc = page.locator("#fx-modal-desc").text_content().strip()
            modal_extended = page.locator("#fx-modal-extended").text_content().strip()
            modal_takeaways = page.locator("#fx-modal-takeaways").is_visible()
            modal_badge = page.locator("#fx-modal-badge").text_content().strip()

            print(f"\n[Verified Article in Modal]:")
            print(f"  Title: '{modal_title}'")
            print(f"  Category: '{modal_cat}'")
            print(f"  Meta: {modal_date} • {modal_readtime}")
            print(f"  Desc: {modal_desc[:60]}...")
            print(f"  Extended: {modal_extended[:60]}...")
            print(f"  Takeaways visible: {modal_takeaways}")
            print(f"  Badge: '{modal_badge}'")

            assert expected_title in modal_title or modal_title in expected_title, f"Title mismatch: {modal_title}"
            assert expected_cat_badge.lower() in modal_cat.lower(), f"Category mismatch: {modal_cat}"
            assert len(modal_desc) > 20, "Modal description too short or empty"
            assert len(modal_extended) > 50, "Modal extended text too short or empty"
            assert modal_takeaways, "Modal takeaways box missing or hidden"

            if cat_filter == "all":
                page.screenshot(path=r"FieldOps_Nexus_Internal\scratch\verified_modal_article1.png")
            elif cat_filter == "documentation" and "API" in expected_title:
                page.screenshot(path=r"FieldOps_Nexus_Internal\scratch\verified_modal_article_doc.png")

            # Test Close with X button
            page.locator("#fx-modal-close").click()
            time.sleep(0.4)
            assert not overlay.is_visible() or overlay.get_attribute("hidden") is not None, "Modal did not close via close button"
            body_overflow_after = page.evaluate("() => document.body.style.overflow")
            assert body_overflow_after == "", f"Body overflow should be restored, got '{body_overflow_after}'"

        print("\n=== 4. TESTING ESCAPE KEY & OUTSIDE CLICK ===")
        # Open card 1 again
        page.locator(f".fx-filter-btn[data-filter='all']").click()
        time.sleep(0.3)
        page.locator(".fx-read-more-link").first.click()
        time.sleep(0.4)
        assert overlay.is_visible(), "Modal not open for Escape test"

        # Press Escape
        page.keyboard.press("Escape")
        time.sleep(0.4)
        assert not overlay.is_visible() or overlay.get_attribute("hidden") is not None, "Modal did not close via Escape key"
        print("Escape key successfully closed modal.")

        # Open card 1 again for outside click test
        page.locator(".fx-read-more-link").first.click()
        time.sleep(0.4)
        assert overlay.is_visible(), "Modal not open for outside click test"

        # Click outside modal (at top-left padding area)
        page.mouse.click(50, 50)
        time.sleep(0.4)
        assert not overlay.is_visible() or overlay.get_attribute("hidden") is not None, "Modal did not close via outside click"
        print("Outside click successfully closed modal.")

        print("\n=== 5. TESTING MOBILE RESPONSIVENESS (375x812) ===")
        mobile_page = browser.new_page(viewport={"width": 375, "height": 812})
        mobile_page.goto("http://localhost:8000/resources/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.0)

        # Open modal on mobile
        mobile_card = mobile_page.locator(".fx-read-more-link").first
        mobile_card.click()
        time.sleep(0.5)

        mobile_overlay = mobile_page.locator("#fx-article-modal-overlay")
        assert mobile_overlay.is_visible(), "Modal not visible on mobile"
        mobile_page.screenshot(path=r"FieldOps_Nexus_Internal\scratch\verified_modal_mobile.png")
        print("Captured verified_modal_mobile.png")

        mobile_page.close()
        browser.close()

        print("\nALL VERIFICATION TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    run_verification()

