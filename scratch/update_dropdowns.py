import os

base_html_path = r"C:\Users\veere\new internal\FieldOps_Nexus_Internal\src\templates\public\base_public.html"

with open(base_html_path, "r", encoding="utf-8") as f:
    content = f.read()

# Verify existing markers
start_desktop_marker = "<!-- 1. Product Mega Menu -->"
end_desktop_marker = "<!-- Mobile Collapsible Menu Drawer -->"

if start_desktop_marker not in content or end_desktop_marker not in content:
    print("ERROR: Desktop mega menu markers not found!")
    exit(1)

# New Desktop Mega Menus HTML
new_desktop_html = """<!-- 1. Product Mega Menu -->
  <div class="fx-mega-menu" id="mega-product" role="dialog" aria-label="Product mega menu">
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
  </div>

  <!-- 2. Solutions Mega Menu -->
  <div class="fx-mega-menu" id="mega-solutions" role="dialog" aria-label="Solutions mega menu">
    <div class="fx-mega-menu-inner">
      <div class="fx-mega-2col-layout">
        <div class="fx-mega-items-col">
          <div class="fx-mega-sec-label">
            <span>BY USE CASE</span>
            <span class="line"></span>
          </div>
          <div class="fx-mega-cards-grid">
            <!-- Item 1: Enterprise Operations -->
            <a href="{% url 'ui:public_solution' 'enterprise-operations' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect>
                  <line x1="9" y1="22" x2="9" y2="22.01"></line>
                  <line x1="15" y1="22" x2="15" y2="22.01"></line>
                  <line x1="8" y1="6" x2="10" y2="6"></line>
                  <line x1="14" y1="6" x2="16" y2="6"></line>
                  <line x1="8" y1="10" x2="10" y2="10"></line>
                  <line x1="14" y1="10" x2="16" y2="10"></line>
                  <line x1="8" y1="14" x2="10" y2="14"></line>
                  <line x1="14" y1="14" x2="16" y2="14"></line>
                  <line x1="8" y1="18" x2="10" y2="18"></line>
                  <line x1="14" y1="18" x2="16" y2="18"></line>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">Enterprise Operations</span>
                <p class="fx-mega-card-desc">Unify complex operations across your organization.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>

            <!-- Item 2: SLA Management -->
            <a href="{% url 'ui:public_solution' 'sla-management' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 2a10 10 0 1 0 10 10"></path>
                  <path d="M12 12l5-5"></path>
                  <circle cx="12" cy="12" r="2"></circle>
                  <path d="M20.2 16.2A10 10 0 0 0 12 2"></path>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">SLA Management</span>
                <p class="fx-mega-card-desc">Monitor and enforce service level agreements at scale.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>

            <!-- Item 3: Multi-Site Management -->
            <a href="{% url 'ui:public_solution' 'multi-site-management' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                  <circle cx="12" cy="10" r="3"></circle>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">Multi-Site Management</span>
                <p class="fx-mega-card-desc">Bring sites, teams, and structures into one connected view.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>

            <!-- Item 4: Connected Data -->
            <a href="{% url 'ui:public_solution' 'connected-data' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">Connected Data</span>
                <p class="fx-mega-card-desc">Connect operational information across teams and locations.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>
          </div>
        </div>

        <!-- Featured Card: Solutions Overview -->
        <div class="fx-mega-feat-card">
          <div>
            <div class="fx-mega-feat-pill">
              <span class="bar"></span>
              <span class="txt">SOLUTIONS OVERVIEW</span>
            </div>
            <h3>FieldOps Solutions</h3>
            <p>Purpose-built solutions to streamline service, assets, and field operations.</p>
          </div>

          <div class="fx-mega-device-wrap">
            <svg class="fx-mega-device-svg" viewBox="0 0 320 200" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <filter id="goldGlowSol" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="6" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                <linearGradient id="screenGradSol" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#0F1E36" />
                  <stop offset="100%" stop-color="#071120" />
                </linearGradient>
                <linearGradient id="bezelGradSol" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#22304A" />
                  <stop offset="100%" stop-color="#121D2F" />
                </linearGradient>
                <linearGradient id="goldBarGradSol" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#FFDF78" />
                  <stop offset="100%" stop-color="#F5C451" />
                </linearGradient>
              </defs>
              <ellipse cx="160" cy="180" rx="125" ry="14" fill="rgba(245, 196, 81, 0.12)" stroke="#F5C451" stroke-width="2" filter="url(#goldGlowSol)" />
              <ellipse cx="160" cy="180" rx="80" ry="8" fill="rgba(245, 196, 81, 0.25)" filter="url(#goldGlowSol)" />
              <polygon points="32,28 288,28 298,168 22,168" fill="url(#bezelGradSol)" stroke="rgba(255,255,255,0.18)" stroke-width="1.5" />
              <polygon points="40,34 280,34 290,162 30,162" fill="url(#screenGradSol)" />
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
              <rect x="214" y="120" width="5.5" height="14" rx="1.5" fill="url(#goldBarGradSol)" />
              <rect x="222" y="112" width="5.5" height="22" rx="1.5" fill="url(#goldBarGradSol)" />
              <rect x="230" y="102" width="5.5" height="32" rx="1.5" fill="url(#goldBarGradSol)" />
              <rect x="238" y="94" width="5.5" height="40" rx="1.5" fill="url(#goldBarGradSol)" />
              <rect x="246" y="84" width="5.5" height="50" rx="1.5" fill="url(#goldBarGradSol)" />
              <rect x="254" y="72" width="5.5" height="62" rx="1.5" fill="url(#goldBarGradSol)" />
              <polygon points="12,176 308,176 300,168 20,168" fill="#1C2738" stroke="rgba(255,255,255,0.15)" stroke-width="1" />
              <polygon points="135,172 185,172 183,175 137,175" fill="#0E1624" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 3. Modules Mega Menu -->
  <div class="fx-mega-menu" id="mega-modules" role="dialog" aria-label="Modules mega menu">
    <div class="fx-mega-menu-inner">
      <div class="fx-mega-2col-layout">
        <div class="fx-mega-items-col">
          <div class="fx-mega-sec-label">
            <span>OPERATIONS &amp; GOVERNANCE</span>
            <span class="line"></span>
          </div>
          <div class="fx-mega-cards-grid">
            <!-- Item 1: Maintenance Management -->
            <a href="{% url 'ui:public_module' 'maintenance-management' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="3"></circle>
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">Maintenance Management</span>
                <p class="fx-mega-card-desc">Stay ahead of downtime with proactive maintenance.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>

            <!-- Item 2: Workforce Management -->
            <a href="{% url 'ui:public_module' 'workforce-management' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">Workforce Management</span>
                <p class="fx-mega-card-desc">Give every field team the context to do their best work.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>

            <!-- Item 3: Analytics & Reporting -->
            <a href="{% url 'ui:public_module' 'analytics-reporting' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="20" x2="18" y2="10"></line>
                  <line x1="12" y1="20" x2="12" y2="4"></line>
                  <line x1="6" y1="20" x2="6" y2="14"></line>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">Analytics &amp; Reporting</span>
                <p class="fx-mega-card-desc">Turn operational data into confident decisions.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>

            <!-- Item 4: Audit & Traceability -->
            <a href="{% url 'ui:public_module' 'audit-traceability' %}" class="fx-mega-card">
              <div class="fx-mega-card-icon">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#F5C451" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                  <circle cx="12" cy="16" r="1.5" fill="#F5C451"></circle>
                </svg>
              </div>
              <div class="fx-mega-card-body">
                <span class="fx-mega-card-title">Audit &amp; Traceability</span>
                <p class="fx-mega-card-desc">Maintain a complete history of all operational activities.</p>
              </div>
              <svg class="fx-mega-card-arrow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </a>
          </div>
        </div>

        <!-- Featured Card: Modules Overview -->
        <div class="fx-mega-feat-card">
          <div>
            <div class="fx-mega-feat-pill">
              <span class="bar"></span>
              <span class="txt">MODULES OVERVIEW</span>
            </div>
            <h3>FieldOps Modules</h3>
            <p>Integrated modules to manage maintenance, workforce, reporting, and operational compliance.</p>
          </div>

          <div class="fx-mega-device-wrap">
            <svg class="fx-mega-device-svg" viewBox="0 0 320 200" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <filter id="goldGlowMod" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="6" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                <linearGradient id="screenGradMod" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#0F1E36" />
                  <stop offset="100%" stop-color="#071120" />
                </linearGradient>
                <linearGradient id="bezelGradMod" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#22304A" />
                  <stop offset="100%" stop-color="#121D2F" />
                </linearGradient>
                <linearGradient id="goldBarGradMod" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#FFDF78" />
                  <stop offset="100%" stop-color="#F5C451" />
                </linearGradient>
              </defs>
              <ellipse cx="160" cy="180" rx="125" ry="14" fill="rgba(245, 196, 81, 0.12)" stroke="#F5C451" stroke-width="2" filter="url(#goldGlowMod)" />
              <ellipse cx="160" cy="180" rx="80" ry="8" fill="rgba(245, 196, 81, 0.25)" filter="url(#goldGlowMod)" />
              <polygon points="32,28 288,28 298,168 22,168" fill="url(#bezelGradMod)" stroke="rgba(255,255,255,0.18)" stroke-width="1.5" />
              <polygon points="40,34 280,34 290,162 30,162" fill="url(#screenGradMod)" />
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
              <rect x="214" y="120" width="5.5" height="14" rx="1.5" fill="url(#goldBarGradMod)" />
              <rect x="222" y="112" width="5.5" height="22" rx="1.5" fill="url(#goldBarGradMod)" />
              <rect x="230" y="102" width="5.5" height="32" rx="1.5" fill="url(#goldBarGradMod)" />
              <rect x="238" y="94" width="5.5" height="40" rx="1.5" fill="url(#goldBarGradMod)" />
              <rect x="246" y="84" width="5.5" height="50" rx="1.5" fill="url(#goldBarGradMod)" />
              <rect x="254" y="72" width="5.5" height="62" rx="1.5" fill="url(#goldBarGradMod)" />
              <polygon points="12,176 308,176 300,168 20,168" fill="#1C2738" stroke="rgba(255,255,255,0.15)" stroke-width="1" />
              <polygon points="135,172 185,172 183,175 137,175" fill="#0E1624" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  </div>\n\n  """

# New Mobile Accordions HTML
start_mobile_marker = "<!-- Product Accordion -->"
end_mobile_marker = "<!-- Direct Links -->"

if start_mobile_marker not in content or end_mobile_marker not in content:
    print("ERROR: Mobile accordion markers not found!")
    exit(1)

new_mobile_html = """<!-- Product Accordion -->
    <div class="fx-mobile-nav-item">
      <button type="button" class="fx-mobile-accordion-trigger" data-fx-mobile-accordion="m-acc-product">
        <span>Product</span>
        {% icon 'chevron-down' 16 %}
      </button>
      <div class="fx-mobile-accordion-content" id="m-acc-product">
        <a href="{% url 'ui:public_product' 'asset-management' %}" class="fx-mobile-sublink">Asset Management</a>
        <a href="{% url 'ui:public_product' 'service-management' %}" class="fx-mobile-sublink">Service Management</a>
        <a href="{% url 'ui:public_product' 'work-order-management' %}" class="fx-mobile-sublink">Work Order Management</a>
        <a href="{% url 'ui:public_product' 'inventory-management' %}" class="fx-mobile-sublink">Inventory Management</a>
      </div>
    </div>

    <!-- Solutions Accordion -->
    <div class="fx-mobile-nav-item">
      <button type="button" class="fx-mobile-accordion-trigger" data-fx-mobile-accordion="m-acc-solutions">
        <span>Solutions</span>
        {% icon 'chevron-down' 16 %}
      </button>
      <div class="fx-mobile-accordion-content" id="m-acc-solutions">
        <a href="{% url 'ui:public_solution' 'enterprise-operations' %}" class="fx-mobile-sublink">Enterprise Operations</a>
        <a href="{% url 'ui:public_solution' 'sla-management' %}" class="fx-mobile-sublink">SLA Management</a>
        <a href="{% url 'ui:public_solution' 'multi-site-management' %}" class="fx-mobile-sublink">Multi-Site Management</a>
        <a href="{% url 'ui:public_solution' 'connected-data' %}" class="fx-mobile-sublink">Connected Data</a>
      </div>
    </div>

    <!-- Modules Accordion -->
    <div class="fx-mobile-nav-item">
      <button type="button" class="fx-mobile-accordion-trigger" data-fx-mobile-accordion="m-acc-modules">
        <span>Modules</span>
        {% icon 'chevron-down' 16 %}
      </button>
      <div class="fx-mobile-accordion-content" id="m-acc-modules">
        <a href="{% url 'ui:public_module' 'maintenance-management' %}" class="fx-mobile-sublink">Maintenance Management</a>
        <a href="{% url 'ui:public_module' 'workforce-management' %}" class="fx-mobile-sublink">Workforce Management</a>
        <a href="{% url 'ui:public_module' 'analytics-reporting' %}" class="fx-mobile-sublink">Analytics &amp; Reporting</a>
        <a href="{% url 'ui:public_module' 'audit-traceability' %}" class="fx-mobile-sublink">Audit &amp; Traceability</a>
      </div>
    </div>\n\n    """

# Perform replacement
p_start = content.find(start_desktop_marker)
p_end = content.find(end_desktop_marker)

updated_content = content[:p_start] + new_desktop_html + content[p_end:]

# Now replace mobile accordions
m_start = updated_content.find(start_mobile_marker)
m_end = updated_content.find(end_mobile_marker)

updated_content = updated_content[:m_start] + new_mobile_html + updated_content[m_end:]

# Bump CSS version from ?v=7.1 to ?v=8.0
updated_content = updated_content.replace("{% static 'css/public.css' %}?v=7.1", "{% static 'css/public.css' %}?v=8.0")
updated_content = updated_content.replace("{% static 'css/public-detail.css' %}?v=7.1", "{% static 'css/public-detail.css' %}?v=8.0")

with open(base_html_path, "w", encoding="utf-8") as f:
    f.write(updated_content)

print("SUCCESS: base_public.html updated cleanly!")

