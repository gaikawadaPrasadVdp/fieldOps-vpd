import re, sys

def verify():
    with open('src/templates/public/resources.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # Verify modal elements
    required_ids = [
        'fx-article-modal-overlay',
        'fx-article-modal',
        'fx-modal-close',
        'fx-modal-category',
        'fx-modal-category-text',
        'fx-modal-title',
        'fx-modal-date',
        'fx-modal-readtime',
        'fx-modal-image',
        'fx-modal-desc',
    ]

    for req_id in required_ids:
        assert f'id="{req_id}"' in html, f"Missing modal element ID: {req_id}"
        print(f"  [OK] Found ID: {req_id}")

    # Verify 6 trigger buttons with data attributes
    triggers = re.findall(r'<button[^>]*class="[^"]*fx-article-modal-trigger[^"]*"[^>]*>', html)
    print(f"\nFound {len(triggers)} modal triggers (expected 6):")
    assert len(triggers) == 6, f"Expected 6 triggers, got {len(triggers)}"

    titles = []
    for i, t in enumerate(triggers):
        match_cat = re.search(r'data-category="([^"]+)"', t)
        match_title = re.search(r'data-title="([^"]+)"', t)
        match_date = re.search(r'data-date="([^"]+)"', t)
        match_read = re.search(r'data-read-time="([^"]+)"', t)
        match_img = re.search(r'data-image="([^"]+)"', t)
        match_desc = re.search(r'data-description="([^"]+)"', t)

        assert match_cat, f"Trigger {i+1} missing category"
        assert match_title, f"Trigger {i+1} missing title"
        assert match_date, f"Trigger {i+1} missing date"
        assert match_read, f"Trigger {i+1} missing read-time"
        assert match_img, f"Trigger {i+1} missing image"
        assert match_desc, f"Trigger {i+1} missing description"

        titles.append(match_title.group(1))
        print(f"  Card {i+1}: [{match_cat.group(1)}] {match_title.group(1)} | {match_date.group(1)} | {match_read.group(1)}")

    assert len(set(titles)) == 6, "Titles are not all unique!"
    print("\nAll 6 cards have unique titles and complete metadata.")

    # Verify CSS in public.css
    with open('src/static/css/public.css', 'r', encoding='utf-8') as f:
        css = f.read()

    css_classes = [
        '.fx-article-overlay',
        '.fx-article-overlay.is-open',
        '.fx-article-overlay[hidden]',
        '.fx-article-modal',
        '.fx-modal-scroll-inner',
        '.fx-modal-close',
        '.fx-modal-category-badge',
        '.fx-modal-title',
        '.fx-modal-meta',
        '.fx-modal-cover-img',
        '.fx-modal-desc',
    ]

    for cls in css_classes:
        assert cls in css, f"Missing CSS rule: {cls}"
        print(f"  [OK] CSS class: {cls}")

    # Verify JS in public.js
    with open('src/static/js/public.js', 'r', encoding='utf-8') as f:
        js = f.read()

    assert 'fxOpenArticleModal' in js, "Missing fxOpenArticleModal in public.js"
    assert 'stopImmediatePropagation' in js, "Missing stopImmediatePropagation in public.js"
    print("  [OK] public.js has fxOpenArticleModal and stopImmediatePropagation")

    print("\nALL CHECKS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    verify()
