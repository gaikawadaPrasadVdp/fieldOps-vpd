import csv

with open('qa_test_cases.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

for r in rows:
    if r.get('Status', '').strip() != 'Passed':
        print("FAIL CASE:")
        for k, v in r.items():
            if v:
                print(f"  {k}: {v}")
