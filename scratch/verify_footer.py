import os
import json
from playwright.sync_api import sync_playwright

def verify_footer():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        
        url = "http://localhost:8000/"
        print(f"Navigating to {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)
        
        # Scroll down to footer
        footer = page.locator(".fx-pub-footer")
        footer.scroll_into_view_if_needed()
        
        # 1. Check Company Column Links
        company_col = page.locator(".fx-footer-grid > div:nth-child(4)")
        company_heading = company_col.locator(".fx-footer-heading").inner_text().strip()
        print(f"Company Heading: {company_heading}")
        
        company_links = company_col.locator(".fx-footer-links li a")
        link_count = company_links.count()
        print(f"Company links count: {link_count}")
        
        links_data = []
        for i in range(link_count):
            link = company_links.nth(i)
            text = link.inner_text().strip()
            href = link.get_attribute("href")
            box = link.bounding_box()
            color = link.evaluate("el => window.getComputedStyle(el).color")
            font_size = link.evaluate("el => window.getComputedStyle(el).fontSize")
            links_data.append({"index": i, "text": text, "href": href, "box": box, "color": color, "fontSize": font_size})
            print(f"  [{i}] {text} -> {href} ({color}, {font_size})")
        
        assert link_count == 5, f"Expected 5 links, got {link_count}"
        assert links_data[3]["text"] == "Careers", f"Expected Careers at index 3, got {links_data[3]['text']}"
        assert links_data[4]["text"] == "Home", f"Expected Home at index 4, got {links_data[4]['text']}"
        assert links_data[4]["href"] == "/", f"Expected Home href to be '/', got {links_data[4]['href']}"
        print("✓ Company column verified: Home is directly below Careers with href='/'")
        
        # 2. Check Get In Touch Rows
        contact_col = page.locator(".fx-footer-grid > div:nth-child(5)")
        contact_heading = contact_col.locator(".fx-footer-heading").inner_text().strip()
        print(f"Contact Heading: {contact_heading}")
        
        contact_rows = contact_col.locator(".fx-footer-contact-row")
        row_count = contact_rows.count()
        print(f"Contact rows count: {row_count}")
        assert row_count == 3, f"Expected 3 contact rows, got {row_count}"
        
        for r in range(row_count):
            row = contact_rows.nth(r)
            icon = row.locator(".fx-footer-contact-icon")
            label = row.locator(".fx-footer-contact-label")
            link = row.locator(".fx-footer-contact-link, .fx-footer-contact-text")
            
            row_box = row.bounding_box()
            icon_box = icon.bounding_box()
            label_box = label.bounding_box()
            link_box = link.bounding_box()
            
            icon_color = icon.evaluate("el => window.getComputedStyle(el).color")
            icon_bg = icon.evaluate("el => window.getComputedStyle(el).backgroundColor")
            icon_border = icon.evaluate("el => window.getComputedStyle(el).borderColor")
            icon_radius = icon.evaluate("el => window.getComputedStyle(el).borderRadius")
            
            lbl_text = label.inner_text().strip()
            lnk_text = link.inner_text().strip()
            lnk_href = link.get_attribute("href")
            
            print(f"\nRow [{r}]: Label='{lbl_text}', Value='{lnk_text}', Href='{lnk_href}'")
            print(f"  Row Box: x={row_box['x']}, y={row_box['y']}, w={row_box['width']}, h={row_box['height']}")
            print(f"  Icon Box: x={icon_box['x']}, y={icon_box['y']}, w={icon_box['width']}, h={icon_box['height']}")
            print(f"  Icon Style: color={icon_color}, bg={icon_bg}, border={icon_border}, radius={icon_radius}")
            print(f"  Label Box: x={label_box['x']}, y={label_box['y']}")
            print(f"  Link Box: x={link_box['x']}, y={link_box['y']}")
            
            # Icon must be on the LEFT of label and link
            assert icon_box['x'] < label_box['x'], "Icon must be on left of label"
            assert icon_box['x'] < link_box['x'], "Icon must be on left of link"
            # Label must be vertically stacked above Link
            assert label_box['y'] < link_box['y'], "Label must be stacked above link"
            # Icon should be vertically aligned with the row (center aligned)
            icon_center_y = icon_box['y'] + icon_box['height'] / 2
            row_center_y = row_box['y'] + row_box['height'] / 2
            assert abs(icon_center_y - row_center_y) < 5, f"Icon not vertically centered with row (diff={abs(icon_center_y - row_center_y)})"
        
        # Check alignment of the 3 rows: icons should share same x position
        row0_icon_x = contact_rows.nth(0).locator(".fx-footer-contact-icon").bounding_box()['x']
        row1_icon_x = contact_rows.nth(1).locator(".fx-footer-contact-icon").bounding_box()['x']
        row2_icon_x = contact_rows.nth(2).locator(".fx-footer-contact-icon").bounding_box()['x']
        assert abs(row0_icon_x - row1_icon_x) < 1, "Row 0 and 1 icons not aligned horizontally"
        assert abs(row0_icon_x - row2_icon_x) < 1, "Row 0 and 2 icons not aligned horizontally"
        print("\n✓ All 3 contact rows have horizontally aligned icons on the LEFT and vertically stacked info on the RIGHT!")
        
        # Check Location icon color is gold rgb(245, 196, 81)
        loc_icon = contact_rows.nth(2).locator(".fx-footer-contact-icon")
        loc_color = loc_icon.evaluate("el => window.getComputedStyle(el).color")
        print(f"Location icon color: {loc_color}")
        assert loc_color in ["rgb(245, 196, 81)", "rgba(245, 196, 81, 1)"], f"Expected gold color, got {loc_color}"
        print("✓ Location icon is gold matching Email and Phone icons!")
        
        # 3. Take screenshots
        out_dir = r"C:\Users\veere\.gemini\antigravity\brain\2070e4fb-022c-4e35-966f-3b108191be6d"
        
        # Desktop Screenshot
        page.set_viewport_size({"width": 1440, "height": 900})
        footer.scroll_into_view_if_needed()
        desktop_shot = os.path.join(out_dir, "footer_desktop.png")
        footer.screenshot(path=desktop_shot)
        print(f"Saved desktop screenshot: {desktop_shot}")
        
        # Tablet Screenshot
        page.set_viewport_size({"width": 768, "height": 1024})
        footer.scroll_into_view_if_needed()
        tablet_shot = os.path.join(out_dir, "footer_tablet.png")
        footer.screenshot(path=tablet_shot)
        print(f"Saved tablet screenshot: {tablet_shot}")
        
        # Mobile Screenshot
        page.set_viewport_size({"width": 375, "height": 812})
        footer.scroll_into_view_if_needed()
        mobile_shot = os.path.join(out_dir, "footer_mobile.png")
        footer.screenshot(path=mobile_shot)
        print(f"Saved mobile screenshot: {mobile_shot}")
        
        browser.close()
        print("\nAll verification passed successfully!")

if __name__ == "__main__":
    verify_footer()
