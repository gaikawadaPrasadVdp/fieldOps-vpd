import os

file_path = r"C:\Users\veere\new internal\FieldOps_Nexus_Internal\src\templates\public\base_public.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Desktop Product Mega Menu Replacement
desktop_start_marker = '<div class="fx-mega-menu" id="mega-product" role="dialog" aria-label="Product mega menu">'
desktop_end_marker = '<!-- 2. Solutions Mega Menu -->'

start_idx = content.find(desktop_start_marker)
end_idx = content.find(desktop_end_marker)

if start_idx == -1 or end_idx == -1:
    print("ERROR: Desktop markers not found!")
    exit(1)

new_product_desktop = """<div class="fx-mega-menu" id="mega-product" role="dialog" aria-label="Product mega menu">
    <div class="fx-mega-menu-inner">
      <div class="fx-mega-2col-layout">
        <div class="fx-mega-items-col">
          <div class="fx-mega-cards-grid">
            <!-- Item 1: Asset Management -->
            <a href="{% url 'ui:public_product' 'asset-management' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                  <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                  <line x1="12" y1="22.08" x2="12" y2="12"></line>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">Asset Management</span>
                <p class="fx-mega-card-desc">Know the condition and history of every critical asset.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>

            <!-- Item 2: Service Management -->
            <a href="{% url 'ui:public_product' 'service-management' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>
                  <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
                  <line x1="9" y1="11" x2="15" y2="11"></line>
                  <line x1="9" y1="15" x2="15" y2="15"></line>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">Service Management</span>
                <p class="fx-mega-card-desc">Deliver consistent service from intake to resolution.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>

            <!-- Item 3: Work Order Management -->
            <a href="{% url 'ui:public_product' 'work-order-management' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                  <line x1="16" y1="2" x2="16" y2="6"></line>
                  <line x1="8" y1="2" x2="8" y2="6"></line>
                  <line x1="3" y1="10" x2="21" y2="10"></line>
                  <path d="M9 15l2 2 4-4"></path>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">Work Order Management</span>
                <p class="fx-mega-card-desc">Plan, assign, and track work with complete clarity.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>

            <!-- Item 4: Inventory Management -->
            <a href="{% url 'ui:public_product' 'inventory-management' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M16.5 9.4L7.5 4.21"></path>
                  <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                  <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                  <line x1="12" y1="22.08" x2="12" y2="12"></line>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">Inventory Management</span>
                <p class="fx-mega-card-desc">Keep essential parts and stock moving efficiently.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>
          </div>
        </div>

        <!-- Featured Card: Product Platform -->
        <div class="fx-mega-feat-card">
          <div>
            <div class="fx-mega-feat-pill">
              <span class="bar"></span>
              <span class="txt">PRODUCT PLATFORM</span>
            </div>
            <h3>FieldOps Nexus</h3>
            <p>Unified, end-to-end operations for service, assets, and field teams.</p>
          </div>

          <div class="fx-mega-device-wrap">
            <svg class="fx-mega-device-svg" viewBox="0 0 320 200" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <filter id="goldGlowProd" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="6" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                <linearGradient id="screenGradProd" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#0F1E36" />
                  <stop offset="100%" stop-color="#071120" />
                </linearGradient>
                <linearGradient id="bezelGradProd" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#22304A" />
                  <stop offset="100%" stop-color="#121D2F" />
                </linearGradient>
                <linearGradient id="goldBarGradProd" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#FFDF78" />
                  <stop offset="100%" stop-color="#F5C451" />
                </linearGradient>
              </defs>
              <ellipse cx="160" cy="180" rx="125" ry="14" fill="rgba(245, 196, 81, 0.12)" stroke="#F5C451" stroke-width="2" filter="url(#goldGlowProd)" />
              <ellipse cx="160" cy="180" rx="80" ry="8" fill="rgba(245, 196, 81, 0.25)" filter="url(#goldGlowProd)" />
              <polygon points="32,28 288,28 298,168 22,168" fill="url(#bezelGradProd)" stroke="rgba(255,255,255,0.18)" stroke-width="1.5" />
              <polygon points="40,34 280,34 290,162 30,162" fill="url(#screenGradProd)" />
              <circle cx="48" cy="44" r="2.5" fill="#F5C451" />
              <text x="56" y="47" fill="#CBD5E1" font-size="7.5" font-weight="600" font-family="system-ui, sans-serif">FieldOps <tspan fill="#F5C451" font-weight="700">Nexus</tspan></text>
              <line x1="42" y1="52" x2="278" y2="52" stroke="rgba(255,255,255,0.08)" stroke-width="1" />
              <rect x="46" y="58" width="105" height="92" rx="4" fill="rgba(11,26,48,0.7)" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
              <text x="54" y="69" fill="#94A3B8" font-size="6.5" font-family="system-ui, sans-serif">Operational Performance</text>
              <circle cx="98" cy="106" r="24" stroke="rgba(255,255,255,0.08)" stroke-width="8" fill="none" />
              <circle cx="98" cy="106" r="24" stroke="#38BDF8" stroke-width="8" stroke-dasharray="38 150" stroke-dashoffset="0" fill="none" />
              <circle cx="98" cy="106" r="24" stroke="#F5C451" stroke-width="8" stroke-dasharray="90 150" stroke-dashoffset="-42" fill="none" />
              <circle cx="98" cy="106" r="14" fill="#091424" />
              <text x="98" y="108" fill="#F8FAFC" font-size="7.5" font-weight="700" text-anchor="middle" font-family="system-ui, sans-serif">98%</text>
              <text x="98" y="115" fill="#94A3B8" font-size="4.5" text-anchor="middle" font-family="system-ui, sans-serif">UPTIME</text>
              <rect x="157" y="58" width="115" height="92" rx="4" fill="rgba(11,26,48,0.7)" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
              <text x="165" y="69" fill="#94A3B8" font-size="6.5" font-family="system-ui, sans-serif">Resource Telemetry</text>
              <line x1="165" y1="78" x2="195" y2="78" stroke="rgba(255,255,255,0.15)" stroke-width="1.5" stroke-linecap="round" />
              <line x1="165" y1="84" x2="185" y2="84" stroke="rgba(255,255,255,0.15)" stroke-width="1.5" stroke-linecap="round" />
              <line x1="165" y1="90" x2="200" y2="90" stroke="rgba(255,255,255,0.15)" stroke-width="1.5" stroke-linecap="round" />
              <line x1="210" y1="134" x2="264" y2="134" stroke="rgba(255,255,255,0.12)" stroke-width="1" />
              <rect x="214" y="120" width="5.5" height="14" rx="1.5" fill="url(#goldBarGradProd)" />
              <rect x="222" y="112" width="5.5" height="22" rx="1.5" fill="url(#goldBarGradProd)" />
              <rect x="230" y="102" width="5.5" height="32" rx="1.5" fill="url(#goldBarGradProd)" />
              <rect x="238" y="94" width="5.5" height="40" rx="1.5" fill="url(#goldBarGradProd)" />
              <rect x="246" y="84" width="5.5" height="50" rx="1.5" fill="url(#goldBarGradProd)" />
              <rect x="254" y="72" width="5.5" height="62" rx="1.5" fill="url(#goldBarGradProd)" />
              <polygon points="12,176 308,176 300,168 20,168" fill="#1C2738" stroke="rgba(255,255,255,0.15)" stroke-width="1" />
              <polygon points="135,172 185,172 183,175 137,175" fill="#0E1624" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  </div>\n\n  """

updated_content = content[:start_idx] + new_product_desktop + content[end_idx:]

# Mobile Product Accordion Replacement
mobile_start_marker = '<div class="fx-mobile-accordion-content" id="m-acc-product">'
mobile_end_marker = '<!-- Solutions Accordion -->'

m_start_idx = updated_content.find(mobile_start_marker)
m_end_idx = updated_content.find(mobile_end_marker)

if m_start_idx == -1 or m_end_idx == -1:
    print("ERROR: Mobile markers not found!")
    exit(1)

new_product_mobile = """<div class="fx-mobile-accordion-content" id="m-acc-product">
        <a href="{% url 'ui:public_product' 'asset-management' %}" class="fx-mobile-sublink">Asset Management</a>
        <a href="{% url 'ui:public_product' 'work-order-management' %}" class="fx-mobile-sublink">Work Order Management</a>
        <a href="{% url 'ui:public_product' 'service-management' %}" class="fx-mobile-sublink">Service Management</a>
        <a href="{% url 'ui:public_product' 'inventory-management' %}" class="fx-mobile-sublink">Inventory Management</a>
      </div>
    </div>\n\n    """

# Notice m_acc_product is inside <div class="fx-mobile-nav-item"> which has its closing </div> before <!-- Solutions Accordion -->
# Let's find </button> before m-acc-product
end_of_div = updated_content.rfind('</div>', m_start_idx, m_end_idx)
# The item container ends with </div> before <!-- Solutions Accordion -->

item_div_end = updated_content.find('</div>', m_start_idx)
container_div_end = updated_content.find('</div>', item_div_end + 6)
# Let's replace just from mobile_start_marker to container_div_end + 6

new_mobile_block = """<div class="fx-mobile-accordion-content" id="m-acc-product">
        <a href="{% url 'ui:public_product' 'asset-management' %}" class="fx-mobile-sublink">Asset Management</a>
        <a href="{% url 'ui:public_product' 'work-order-management' %}" class="fx-mobile-sublink">Work Order Management</a>
        <a href="{% url 'ui:public_product' 'service-management' %}" class="fx-mobile-sublink">Service Management</a>
        <a href="{% url 'ui:public_product' 'inventory-management' %}" class="fx-mobile-sublink">Inventory Management</a>
      </div>
    </div>"""

# Replace between m_start_idx and m_end_idx safely
# Let's slice from m_start_idx to m_end_idx
updated_content = updated_content[:m_start_idx] + new_mobile_block + "\n\n    " + updated_content[m_end_idx:]

with open(file_path, "w", encoding="utf-8") as f:
    f.write(updated_content)

print("SUCCESS: Product dropdown menu updated in base_public.html!")

