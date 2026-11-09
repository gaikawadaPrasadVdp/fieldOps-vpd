import time
from playwright.sync_api import sync_playwright

def measure():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto("http://localhost:8000/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.5)

        btn = page.locator('button[data-fx-mega-trigger="modules"]')
        btn.hover()
        time.sleep(0.5)

        menu = page.locator('#mega-modules').bounding_box()
        label = page.locator('#mega-modules .fx-mega-sec-label').bounding_box()
        grid = page.locator('#mega-modules .fx-mega-cards-grid').bounding_box()
        feat = page.locator('#mega-modules .fx-mega-feat-card').bounding_box()
        first_card = page.locator('#mega-modules .fx-mega-card').first.bounding_box()

        print(f"Menu: {menu}")
        print(f"Label: {label}")
        print(f"Grid: {grid}")
        print(f"Feat Card: {feat}")
        print(f"First Card: {first_card}")

        if label and grid:
            gap = grid['y'] - (label['y'] + label['height'])
            print(f"Current vertical gap between OPERATIONS & GOVERNANCE and cards: {gap}px")

        browser.close()

if __name__ == "__main__":
    measure()

