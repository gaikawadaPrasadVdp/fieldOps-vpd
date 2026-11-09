import urllib.request
import urllib.error

def check():
    urls_to_test = [
        "http://localhost:8000/",
        "http://localhost:8000/product/asset-management/",
        "http://localhost:8000/product/service-management/",
        "http://localhost:8000/product/work-order-management/",
        "http://localhost:8000/product/inventory-management/",
        "http://localhost:8000/solutions/enterprise-operations/",
        "http://localhost:8000/solutions/sla-management/",
        "http://localhost:8000/solutions/multi-site-management/",
        "http://localhost:8000/solutions/connected-data/",
        "http://localhost:8000/modules/maintenance-management/",
        "http://localhost:8000/modules/workforce-management/",
        "http://localhost:8000/modules/analytics-reporting/",
        "http://localhost:8000/modules/audit-traceability/",
    ]

    all_passed = True
    print("Testing URLs...")
    for u in urls_to_test:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
                print(f"[{status}] {u}")
                if status != 200:
                    all_passed = False
        except urllib.error.HTTPError as e:
            print(f"[{e.code}] {u} - ERROR: {e.reason}")
            all_passed = False
        except Exception as e:
            print(f"[FAIL] {u} - {e}")
            all_passed = False

    print("\nChecking Home Page HTML contents...")
    with urllib.request.urlopen("http://localhost:8000/") as resp:
        html = resp.read().decode("utf-8")
        
        checks = [
            ("id=\"mega-product\"", "Mega Product Container"),
            ("id=\"mega-solutions\"", "Mega Solutions Container"),
            ("id=\"mega-modules\"", "Mega Modules Container"),
            ("Asset Management", "Product Item 1"),
            ("Service Management", "Product Item 2"),
            ("Work Order Management", "Product Item 3"),
            ("Inventory Management", "Product Item 4"),
            ("Enterprise Operations", "Solution Item 1"),
            ("SLA Management", "Solution Item 2"),
            ("Multi-Site Management", "Solution Item 3"),
            ("Connected Data", "Solution Item 4"),
            ("Maintenance Management", "Module Item 1"),
            ("Workforce Management", "Module Item 2"),
            ("Analytics &amp; Reporting", "Module Item 3"),
            ("Audit &amp; Traceability", "Module Item 4"),
            ("id=\"m-acc-product\"", "Mobile Product Accordion"),
            ("id=\"m-acc-solutions\"", "Mobile Solutions Accordion"),
            ("id=\"m-acc-modules\"", "Mobile Modules Accordion"),
        ]

        for pattern, desc in checks:
            found = pattern in html
            print(f"[{'PASS' if found else 'FAIL'}] {desc}: '{pattern}'")
            if not found:
                all_passed = False

    print(f"\nOverall Result: {'ALL CHECKS PASSED' if all_passed else 'SOME CHECKS FAILED'}")

if __name__ == "__main__":
    check()

