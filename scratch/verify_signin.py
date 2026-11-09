import os
import sys
from playwright.sync_api import sync_playwright

def test_signin_page():
    viewports = [
        ("desktop_1920", 1920, 1080, True),
        ("desktop_1440", 1440, 900, True),
        ("desktop_1366", 1366, 768, True),
        ("tablet_1024", 1024, 768, True),
        ("tablet_768", 768, 1024, True),
        ("mobile_430", 430, 932, False),
        ("mobile_390", 390, 844, False),
        ("mobile_375", 375, 667, False),
        ("mobile_320", 320, 568, False),
    ]

    out_dir = r"C:\Users\veere\.gemini\antigravity\brain\2070e4fb-022c-4e35-966f-3b108191be6d"
    login_url = "http://localhost:8000/accounts/login/"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # 1. Initial State Test at 1440px
        print("\n=== 1. Initial State Check (Desktop 1440px) ===")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(500)

        alert = page.locator("#fx-login-error-alert")
        is_visible = alert.is_visible()
        print(f"Error alert visible on initial load: {is_visible}")
        assert not is_visible, "Error alert should be hidden initially"

        # Check no error text beside or below inputs
        side_errors = page.locator(".field-error-message, .invalid-feedback, .text-danger:not(.fx-req)").all()
        visible_errors = [e for e in side_errors if e.is_visible()]
        print(f"Visible field error elements on initial load: {len(visible_errors)}")
        assert len(visible_errors) == 0, f"Expected 0 visible field error elements, got {len(visible_errors)}"
        print("✓ Initial load clean: no error alerts, no field error text")

        # 2. Invalid Credentials Submission Test
        print("\n=== 2. Invalid Credentials Submission Test ===")
        # Fill incorrect email and password (matching user screenshot)
        page.fill("#id_username", "rejrekj")
        page.fill("#id_password", "jrerekrkemr")
        page.click("button[type='submit']")
        page.wait_for_timeout(1000)

        # Verify Alert Presence, Position, Text, Styling
        assert alert.is_visible(), "Error alert must be visible after failed login"
        alert_text = alert.locator(".fx-login-error-text").inner_text().strip()
        print(f"Alert text: '{alert_text}'")
        expected_msg = "Invalid email or password. Please check your credentials and try again."
        assert alert_text == expected_msg, f"Expected '{expected_msg}', got '{alert_text}'"

        # Position Check: below title/subtitle, above Email Address field
        title_box = page.locator(".fx-login-title").bounding_box()
        sub_box = page.locator(".fx-login-subtitle").bounding_box()
        alert_box = alert.bounding_box()
        email_group = page.locator(".fx-login-group").first
        email_box = email_group.bounding_box()

        print(f"Subtitle Bottom Y: {sub_box['y'] + sub_box['height']}")
        print(f"Alert Top Y: {alert_box['y']}, Bottom Y: {alert_box['y'] + alert_box['height']}")
        print(f"Email Group Top Y: {email_box['y']}")

        assert alert_box['y'] >= sub_box['y'] + sub_box['height'] - 5, "Alert must be below subtitle"
        assert alert_box['y'] + alert_box['height'] <= email_box['y'] + 5, "Alert must be above Email field"

        # Check Alert Styling
        bg_color = alert.evaluate("el => window.getComputedStyle(el).backgroundColor")
        text_color = alert.evaluate("el => window.getComputedStyle(el).color")
        border_radius = alert.evaluate("el => window.getComputedStyle(el).borderRadius")
        border_color = alert.evaluate("el => window.getComputedStyle(el).borderColor")
        print(f"Alert Styling: bg={bg_color}, color={text_color}, border={border_color}, radius={border_radius}")
        assert "254" in bg_color and "242" in bg_color, f"Expected light-red bg, got {bg_color}"
        assert alert.locator(".fx-login-error-icon").is_visible(), "Warning icon must be visible in alert"

        # Check NO error message beside or below input fields
        wrapper_children = page.locator(".fx-input-wrapper").all()
        for idx, wrap in enumerate(wrapper_children):
            errs = wrap.locator(".field-error-message, .invalid-feedback, .text-danger").all()
            vis = [e for e in errs if e.is_visible()]
            assert len(vis) == 0, f"Field wrapper {idx} has visible error messages: {vis}"

        card_field_errs = page.locator(".fx-login-card .field-error-message, .fx-login-card .invalid-feedback").all()
        vis_card_errs = [e for e in card_field_errs if e.is_visible()]
        assert len(vis_card_errs) == 0, f"Found visible field errors inside card: {vis_card_errs}"
        print("✓ Alert verified: correctly positioned, exact text, beautiful light-red styling, zero input field errors")

        # 3. Test Password Toggle
        print("\n=== 3. Password Visibility Toggle Test ===")
        pw_input = page.locator("#id_password")
        toggle_btn = page.locator("#fx-pw-toggle")
        
        assert pw_input.get_attribute("type") == "password"
        toggle_btn.click()
        page.wait_for_timeout(200)
        assert pw_input.get_attribute("type") == "text", "Password input should switch to text"
        toggle_btn.click()
        page.wait_for_timeout(200)
        assert pw_input.get_attribute("type") == "password", "Password input should switch back to password"
        print("✓ Password toggle working correctly")

        context.close()

        # 4. Comprehensive Responsive Tests Across All 9 Viewports
        print("\n=== 4. Testing All 9 Viewport Sizes ===")
        for name, width, height, should_have_left_col in viewports:
            ctx = browser.new_context(viewport={"width": width, "height": height})
            pg = ctx.new_page()
            
            # Load page with error alert active
            pg.goto(login_url, wait_until="domcontentloaded", timeout=15000)
            pg.fill("#id_username", "invalid@fieldops.io")
            pg.fill("#id_password", "wrongpass123")
            pg.click("button[type='submit']")
            pg.wait_for_timeout(800)

            # Check horizontal overflow
            scroll_width = pg.evaluate("() => document.documentElement.scrollWidth")
            client_width = pg.evaluate("() => document.documentElement.clientWidth")
            print(f"[{name}] Viewport {width}x{height}: scrollWidth={scroll_width}, clientWidth={client_width}")
            assert scroll_width <= client_width + 1, f"Horizontal overflow detected on {name}: {scroll_width} > {client_width}"

            # Check left column
            left_col = pg.locator("aside.fx-auth-aside")
            left_visible = left_col.is_visible()
            if should_have_left_col:
                assert left_visible, f"Left branding column should be visible on {name} ({width}px)"
            else:
                assert not left_visible, f"Left branding column should be hidden on {name} ({width}px)"

            # Check mobile brand header
            mobile_header = pg.locator(".fx-mobile-brand-header")
            header_visible = mobile_header.is_visible()
            if not should_have_left_col:
                assert header_visible, f"Mobile brand header should be visible on {name} ({width}px)"
            else:
                assert not header_visible, f"Mobile brand header should be hidden on {name} ({width}px)"

            # Check login card fits and is centered
            card = pg.locator(".fx-login-card")
            card_box = card.bounding_box()
            assert card_box['width'] <= width, f"Card width {card_box['width']} exceeds viewport {width}"
            assert card_box['x'] >= 0, f"Card x position {card_box['x']} is offscreen"

            # Check error alert wraps and fits
            alert_el = pg.locator("#fx-login-error-alert")
            assert alert_el.is_visible(), f"Error alert should be visible on {name}"
            alert_b = alert_el.bounding_box()
            assert alert_b['width'] <= card_box['width'], f"Alert width {alert_b['width']} exceeds card {card_box['width']}"

            # Check submit button fits
            btn = pg.locator(".fx-login-submit-btn")
            btn_box = btn.bounding_box()
            assert btn_box['width'] <= card_box['width'], f"Button width {btn_box['width']} exceeds card {card_box['width']}"

            # Save screenshot
            shot_path = os.path.join(out_dir, f"login_{name}.png")
            pg.screenshot(path=shot_path, full_page=True)
            print(f"  ✓ Saved screenshot: {shot_path}")

            ctx.close()

        browser.close()
        print("\nAll Sign-In error presentation and responsive tests PASSED successfully!")

if __name__ == "__main__":
    test_signin_page()

