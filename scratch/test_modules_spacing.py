import time
from playwright.sync_api import sync_playwright

test_css = """
#mega-modules .fx-mega-menu-inner {
  padding: 20px 28px !important;
}

#mega-modules .fx-mega-2col-layout {
  align-items: center !important;
  gap: 28px !important;
}

#mega-modules .fx-mega-items-col {
  display: flex !important;
  flex-direction: column !important;
  justify-content: flex-start !important;
  gap: 12px !important;
}

#mega-modules .fx-mega-sec-label {
  margin-bottom: 0 !important;
}

#mega-modules .fx-mega-cards-grid {
  gap: 14px !important;
}

#mega-modules .fx-mega-feat-card {
  padding: 18px 20px 14px 20px !important;
}

#mega-modules .fx-mega-device-svg {
  max-width: 250px !important;
}
"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8000/", wait_until="domcontentloaded", timeout=15000)
    time.sleep(1.0)

    page.add_style_tag(content=test_css)

    btn = page.locator('button[data-fx-mega-trigger="modules"]')
    btn.hover()
    time.sleep(0.5)

    menu = page.locator('#mega-modules').bounding_box()
    label = page.locator('#mega-modules .fx-mega-sec-label').bounding_box()
    grid = page.locator('#mega-modules .fx-mega-cards-grid').bounding_box()
    feat = page.locator('#mega-modules .fx-mega-feat-card').bounding_box()

    print(f"Menu: {menu}")
    print(f"Label: {label}")
    print(f"Grid: {grid}")
    print(f"Feat Card: {feat}")
    if label and grid:
        gap = grid['y'] - (label['y'] + label['height'])
        print(f"New vertical gap between OPERATIONS & GOVERNANCE and cards: {gap}px")

    screenshot_path = r"C:\Users\veere\new internal\FieldOps_Nexus_Internal\scratch\test_modules_spacing.png"
    page.screenshot(path=screenshot_path)
    print("Screenshot saved to", screenshot_path)

    browser.close()

