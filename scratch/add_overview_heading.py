path = r"C:\Users\veere\new internal\FieldOps_Nexus_Internal\src\templates\public\base_public.html"

with open(path, "r", encoding="utf-8") as f:
    c = f.read()

target = """        <div class="fx-mega-items-col">
          <div class="fx-mega-cards-grid">"""

replacement = """        <div class="fx-mega-items-col">
          <div class="fx-mega-sec-label">
            <span>OVERVIEW</span>
            <span class="line"></span>
          </div>
          <div class="fx-mega-cards-grid">"""

if target in c:
    c = c.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(c)
    print("SUCCESS: Added OVERVIEW heading to Product dropdown")
else:
    print("ERROR: Target not found")

