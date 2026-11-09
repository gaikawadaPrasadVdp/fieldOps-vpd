import re

with open(r"FieldOps_Nexus_Internal\src\templates\public\resources.html", "r", encoding="utf-8") as f:
    content = f.read()

# Let's split by <div class="fx-resource-card-col"
cards = content.split('<div class="fx-resource-card-col"')
print(f"Total card chunks: {len(cards) - 1}")

for i, chunk in enumerate(cards[1:], 1):
    category_match = re.search(r'data-category="([^"]+)"', chunk)
    title_match = re.search(r'<h3 class="fx-card-title">(.*?)</h3>', chunk, re.DOTALL)
    desc_match = re.search(r'<p class="fx-card-desc">(.*?)</p>', chunk, re.DOTALL)
    extended_match = re.search(r'<p class="fx-card-extended-text">(.*?)</p>', chunk, re.DOTALL)
    takeaways_match = re.search(r'<div class="fx-card-takeaways-box">(.*?)</div>\s*<div class="fx-card-expanded-meta">', chunk, re.DOTALL)
    
    cat = category_match.group(1) if category_match else "N/A"
    title = " ".join(title_match.group(1).split()) if title_match else "N/A"
    desc = " ".join(desc_match.group(1).split()) if desc_match else "N/A"
    extended = " ".join(extended_match.group(1).split()) if extended_match else "None"
    has_takeaways = bool(takeaways_match)
    
    print(f"\n--- Card {i}: [{cat}] {title} ---")
    print(f"Desc: {desc[:80]}...")
    print(f"Extended text length: {len(extended)}")
    print(f"Has takeaways: {has_takeaways}")

