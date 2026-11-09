css_file = r"C:\Users\veere\new internal\FieldOps_Nexus_Internal\src\static\css\public.css"

with open(css_file, "r", encoding="utf-8") as f:
    css_content = f.read()

# Marker to prevent duplicate appending
marker = "/* ==========================================================================\n   FieldOps Nexus - Premium 2x2 Dropdown Mega-Menus (Product, Solutions, Modules)\n   ========================================================================== */"

if marker in css_content:
    print("Already appended, removing previous block first...")
    idx = css_content.find(marker)
    css_content = css_content[:idx].rstrip() + "\n\n"

new_css = """/* ==========================================================================
   FieldOps Nexus - Premium 2x2 Dropdown Mega-Menus (Product, Solutions, Modules)
   ========================================================================== */

.fx-mega-menu {
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  width: calc(100% - 64px);
  max-width: 1240px;
  background-color: #08172F !important;
  border: 1px solid rgba(255, 255, 255, 0.09) !important;
  border-radius: 20px !important;
  box-shadow: 0 28px 70px -12px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.05) !important;
  z-index: 1050;
  display: none;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.22s cubic-bezier(0.16, 1, 0.3, 1), transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  box-sizing: border-box;
}

/* Invisible bridge so mouse transition between header and menu never flickers */
.fx-mega-menu::before {
  content: '';
  position: absolute;
  top: -16px;
  left: 0;
  right: 0;
  height: 16px;
  pointer-events: auto;
}

.fx-mega-menu.is-active {
  display: block !important;
  opacity: 1 !important;
  pointer-events: auto !important;
}

.fx-mega-menu-inner {
  padding: 24px 28px !important;
  max-width: 100% !important;
  margin: 0 !important;
  box-sizing: border-box;
}

.fx-mega-2col-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
  align-items: stretch;
}

@media (min-width: 1024px) {
  .fx-mega-2col-layout {
    grid-template-columns: 1fr 330px;
    gap: 28px;
  }
}

.fx-mega-items-col {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

/* Section label above 2x2 grid (Solutions: BY USE CASE, Modules: OPERATIONS & GOVERNANCE) */
.fx-mega-sec-label {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  color: #F5C451;
  text-transform: uppercase;
  line-height: 1;
}

.fx-mega-sec-label .line {
  width: 32px;
  height: 2px;
  background: #F5C451;
  border-radius: 2px;
  display: inline-block;
}

/* 2x2 Grid of item cards */
.fx-mega-cards-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}

@media (min-width: 640px) {
  .fx-mega-cards-grid {
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
}

/* Individual Item Card */
.fx-mega-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-radius: 14px;
  background: rgba(14, 30, 56, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.08);
  text-decoration: none !important;
  transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  min-height: 84px;
  box-sizing: border-box;
}

.fx-mega-card:hover {
  background: rgba(18, 38, 70, 0.92);
  border-color: #F5C451;
  box-shadow: 0 0 18px rgba(245, 196, 81, 0.32), inset 0 0 12px rgba(245, 196, 81, 0.05);
  transform: translateY(-2px);
}

/* Icon container */
.fx-mega-card-icon {
  width: 48px;
  height: 48px;
  min-width: 48px;
  border-radius: 12px;
  background: #081528;
  border: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #F5C451;
  flex-shrink: 0;
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.fx-mega-card:hover .fx-mega-card-icon {
  border-color: rgba(245, 196, 81, 0.45);
  background: #0B1D38;
  transform: scale(1.04);
}

/* Card Text Body */
.fx-mega-card-body {
  display: flex;
  flex-direction: column;
  justify-content: center;
  flex: 1;
  min-width: 0;
}

.fx-mega-card-title {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #FFFFFF;
  line-height: 1.3;
  margin-bottom: 3px;
  transition: color 0.18s ease;
}

.fx-mega-card-desc {
  font-size: 12.5px;
  line-height: 1.4;
  color: #94A3B8;
  margin: 0;
  transition: color 0.18s ease;
}

.fx-mega-card:hover .fx-mega-card-desc {
  color: #CBD5E1;
}

/* Right Chevron Arrow */
.fx-mega-card-arrow {
  color: #94A3B8;
  flex-shrink: 0;
  margin-left: auto;
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), color 0.2s ease;
}

.fx-mega-card:hover .fx-mega-card-arrow {
  color: #F5C451;
  transform: translateX(4px);
}

/* Featured Right Card */
.fx-mega-feat-card {
  background: rgba(13, 28, 54, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 22px 20px 18px 20px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.35);
  box-sizing: border-box;
}

.fx-mega-feat-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.fx-mega-feat-pill .bar {
  width: 14px;
  height: 2px;
  background: #F5C451;
  border-radius: 2px;
  display: inline-block;
}

.fx-mega-feat-pill .txt {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #F5C451;
  text-transform: uppercase;
}

.fx-mega-feat-card h3 {
  font-size: 20px;
  font-weight: 700;
  color: #FFFFFF;
  line-height: 1.3;
  margin: 0 0 6px 0;
}

.fx-mega-feat-card p {
  font-size: 12.5px;
  color: #94A3B8;
  line-height: 1.45;
  margin: 0 0 12px 0;
}

/* Device Preview SVG inside Featured Card */
.fx-mega-device-wrap {
  width: 100%;
  position: relative;
  margin-top: auto;
  display: flex;
  justify-content: center;
}

.fx-mega-device-svg {
  width: 100%;
  max-width: 300px;
  height: auto;
  display: block;
  filter: drop-shadow(0 10px 20px rgba(0, 0, 0, 0.5));
}
"""

with open(css_file, "w", encoding="utf-8") as f:
    f.write(css_content + "\n\n" + new_css + "\n")

print("SUCCESS: public.css updated cleanly!")

