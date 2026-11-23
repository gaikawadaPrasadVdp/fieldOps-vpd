import requests, re, sys

BASE = 'http://localhost:8080'

urls = [
    '/',
    '/features/',
    '/product/',
    '/solutions/',
    '/platform/',
    '/resources/',
    '/about/',
    '/contact-sales/',
    '/legal/privacy-policy/',
    '/legal/terms-of-service/',
    '/legal/disclaimer/',
    '/legal/cookie-policy/',
]

# import catalog slugs
from apps.ui.public_catalog import PRODUCT_SLUGS, SOLUTIONS_SLUGS, MODULE_SLUGS

for slug in PRODUCT_SLUGS:
    urls.append(f'/product/{slug}/')
for slug in SOLUTIONS_SLUGS:
    urls.append(f'/solutions/{slug}/')
for slug in MODULE_SLUGS:
    urls.append(f'/platform/{slug}/')

missing = []
for path in urls:
    url = BASE + path
    try:
        r = requests.get(url, timeout=5)
        html = r.text
    except Exception as e:
        missing.append((path, f'Error: {e}'))
        continue
    # checks
    checks = {
        'meta_description': bool(re.search(r'<meta\s+name=["\"]?description["\"]?[^>]*>', html, re.I)),
        'meta_robots': bool(re.search(r'<meta\s+name=["\"]?robots["\"]?[^>]*>', html, re.I)),
        'canonical': bool(re.search(r'<link\s+rel=["\"]?canonical["\"]?[^>]*>', html, re.I)),
        'og_title': bool(re.search(r'<meta\s+property=["\"]?og:title["\"]?[^>]*>', html, re.I)),
        'og_description': bool(re.search(r'<meta\s+property=["\"]?og:description["\"]?[^>]*>', html, re.I)),
        'og_image': bool(re.search(r'<meta\s+property=["\"]?og:image["\"]?[^>]*>', html, re.I)),
        'twitter_card': bool(re.search(r'<meta\s+name=["\"]?twitter:card["\"]?[^>]*>', html, re.I)),
    }
    for name, ok in checks.items():
        if not ok:
            missing.append((path, f'Missing {name}'))
            break

if missing:
    print('SEO issues found:')
    for path, issue in missing:
        print(f'{path}: {issue}')
    sys.exit(1)
else:
    print('All pages have required SEO metadata.')
    sys.exit(0)

