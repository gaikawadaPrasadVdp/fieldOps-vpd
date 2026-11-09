import re

with open(r"FieldOps_Nexus_Internal\src\templates\public\resources.html", "r", encoding="utf-8") as f:
    text = f.read()

# Let's extract each card
card_pattern = re.compile(r'<!-- Card (\d+): (.*?) -->\s*<div class="fx-resource-card-col" data-category="([^"]+)">(.*?)</div>\s*(?=<!-- Card|\Z)', re.DOTALL)
cards = card_pattern.findall(text)
print(f"Matched {len(cards)} cards by comment header")
for num, comment, cat, body in cards:
    print(f"Card {num}: [{cat}] {comment}")

