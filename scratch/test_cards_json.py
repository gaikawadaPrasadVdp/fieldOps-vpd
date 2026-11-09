import json

with open(r"FieldOps_Nexus_Internal\scratch\extracted_cards.json", "r", encoding="utf-8") as f:
    cards = json.load(f)

print(f"Loaded {len(cards)} cards.")
for c in cards:
    print(f"- {c['title']} ({c['cat_badge']})")

