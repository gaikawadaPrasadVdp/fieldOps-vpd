import os
import time
from playwright.sync_api import sync_playwright

def test_variants():
    out_dir = r"C:\Users\veere\new internal\FieldOps_Nexus_Internal\scratch"

    variants = [
        {
            "name": "variant_A_compact_flex_start",
            "css": """
                #mega-product .fx-mega-menu-inner {
                    padding: 22px 28px !important;
                }
                #mega-product .fx-mega-items-col {
                    justify-content: flex-start !important;
                    gap: 14px !important;
                }
                #mega-product .fx-mega-sec-label {
                    margin-bottom: 0 !important;
                }
                #mega-product .fx-mega-cards-grid {
                    gap: 14px !important;
                }
                #mega-product .fx-mega-feat-card {
                    padding: 20px 20px 16px 20px !important;
                }
                #mega-product .fx-mega-device-svg {
                    max-width: 260px !important;
                }
            """
        },
        {
            "name": "variant_B_centered_balanced",
            "css": """
                #mega-product .fx-mega-menu-inner {
                    padding: 22px 28px !important;
                }
                #mega-product .fx-mega-items-col {
                    justify-content: center !important;
                    gap: 14px !important;
                }
                #mega-product .fx-mega-sec-label {
                    margin-bottom: 0 !important;
                }
                #mega-product .fx-mega-cards-grid {
                    gap: 14px !important;
                }
                #mega-product .fx-mega-feat-card {
                    padding: 20px 20px 16px 20px !important;
                }
                #mega-product .fx-mega-device-svg {
                    max-width: 270px !important;
                }
            """
        },
        {
            "name": "variant_C_aligned_top",
            "css": """
                #mega-product .fx-mega-menu-inner {
                    padding: 20px 28px !important;
                }
                #mega-product .fx-mega-2col-layout {
                    align-items: center !important;
                    gap: 28px !important;
                }
                #mega-product .fx-mega-items-col {
                    justify-content: flex-start !important;
                    gap: 12px !important;
                }
                #mega-product .fx-mega-sec-label {
                    margin-bottom: 0 !important;
                }
                #mega-product .fx-mega-cards-grid {
                    gap: 14px !important;
                }
                #mega-product .fx-mega-feat-card {
                    padding: 18px 20px 14px 20px !important;
                }
                #mega-product .fx-mega-device-svg {
                    max-width: 250px !important;
                }
            """
        }
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto("http://localhost:8000/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.5)

        for v in variants:
            # Inject CSS
            page.add_style_tag(content=v["css"])
            prod_btn = page.locator('button[data-fx-mega-trigger="product"]')
            prod_btn.hover()
            time.sleep(0.4)

            # Hover first card
            page.locator('#mega-product .fx-mega-card').first.hover()
            time.sleep(0.3)

            ss_path = os.path.join(out_dir, f"{v['name']}.png")
            page.screenshot(path=ss_path)
            print(f"Captured {v['name']}: {ss_path}")

        browser.close()

if __name__ == "__main__":
    test_variants()

