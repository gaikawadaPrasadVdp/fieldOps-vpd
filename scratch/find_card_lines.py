with open(r"FieldOps_Nexus_Internal\src\templates\public\resources.html", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
# Let's inspect where cards start and end
for i, line in enumerate(lines):
    if "<!-- Card" in line or 'class="fx-resources-grid"' in line or 'class="fx-faq-section"' in line or 'id="fx-article-modal-overlay"' in line:
        print(f"Line {i+1}: {line.strip()}")

