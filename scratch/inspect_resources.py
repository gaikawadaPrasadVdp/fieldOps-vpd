import re

with open(r"FieldOps_Nexus_Internal\src\templates\public\resources.html", "r", encoding="utf-8") as f:
    content = f.read()

# Find all cards
pattern = re.compile(
    r'<div class="fx-resource-card-col"\s+data-category="([^"]+)".*?'
    r'<h3 class="fx-card-title">(.*?)</h3>.*?'
    r'(?=<div class="fx-resource-card-col"|\Z)',
    re.DOTALL
)

matches = pattern.findall(content)
print(f"Total cards matched: {len(matches)}")
for i, (cat, title) in enumerate(matches, 1):
    clean_title = " ".join(title.split())
    print(f"{i}. [{cat}] {clean_title}")

