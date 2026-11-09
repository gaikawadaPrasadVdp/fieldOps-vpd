import re
import json

with open(r"FieldOps_Nexus_Internal\src\templates\public\resources.html", "r", encoding="utf-8") as f:
    text = f.read()

# Split into cards
grid_content = text[text.find('<div class="fx-resources-grid">'):text.find('</section>', text.find('<div class="fx-resources-grid">'))]

card_blocks = re.findall(r'<!-- (Card \d+: [^\n]+) -->(.*?)(?=<!-- Card|\Z)', grid_content, re.DOTALL)
print(f"Extracted {len(card_blocks)} cards.")

card_list = []
for header, block in card_blocks:
    cat_match = re.search(r'data-category="([^"]+)"', block)
    img_match = re.search(r'<img\s+src="([^"]+)"\s+alt="([^"]*)"', block)
    cat_badge = re.search(r'<span class="fx-card-category">(.*?)</span>', block)
    read_time = re.search(r'<span class="fx-card-read-time">(.*?)</span>', block)
    title = re.search(r'<h3 class="fx-card-title">(.*?)</h3>', block, re.DOTALL)
    desc = re.search(r'<p class="fx-card-desc">(.*?)</p>', block, re.DOTALL)
    extended = re.search(r'<p class="fx-card-extended-text">(.*?)</p>', block, re.DOTALL)
    takeaways = re.search(r'<div class="fx-card-takeaways-box">(.*?)</div>\s*<div class="fx-card-expanded-meta">', block, re.DOTALL)
    badge = re.search(r'<span class="fx-badge-best-practice">(.*?)</span>', block)
    date = re.search(r'<span class="fx-card-date">(.*?)</span>', block)

    card_info = {
        "header": header,
        "category_slug": cat_match.group(1) if cat_match else "",
        "img_src": img_match.group(1) if img_match else "",
        "img_alt": img_match.group(2) if img_match else "",
        "cat_badge": cat_badge.group(1) if cat_badge else "",
        "read_time": read_time.group(1) if read_time else "",
        "title": " ".join(title.group(1).split()) if title else "",
        "desc": " ".join(desc.group(1).split()) if desc else "",
        "extended": " ".join(extended.group(1).split()) if extended else "",
        "takeaways_html": takeaways.group(1).strip() if takeaways else "",
        "badge": badge.group(1) if badge else "",
        "date": date.group(1) if date else "",
    }
    card_list.append(card_info)

with open(r"FieldOps_Nexus_Internal\scratch\extracted_cards.json", "w", encoding="utf-8") as f:
    json.dump(card_list, f, indent=2)

print("Saved to extracted_cards.json")

