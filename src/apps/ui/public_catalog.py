"""
FieldOps Nexus — Public Marketing and Product Catalog
Provides rich metadata, capability cards, metrics, and photography mappings
for Product, Solutions, and Modules detail pages.
"""

DETAIL_PAGES = {
    "organization-management": {
        "title": "Organization Management",
        "subtitle": "ENTERPRISE HIERARCHY & SITE CONFIGURATION",
        "tagline": "Bring sites, teams, zones, and business units into one connected view.",
        "description": "Define and manage your entire organizational structure — from enterprise groups and regional divisions down to individual sites, departments, and teams. Control access boundaries, asset ownership, and workforce allocation with precision.",
        "image_path": "images/module-organization.jpg",
        "overlay_label": "Enterprise Multi-Site Architecture Active",
        "metrics": [
            ["12+", "Hierarchy Levels", "Multi-tenant boundaries, regional divisions, plant sites, and zones"],
            ["100%", "Role Boundary Isolation", "Granular RBAC enforcing operational jurisdiction and audit controls"],
            ["Live", "Site Fleet Telemetry", "Consolidated multi-facility situational awareness in real time"],
        ],
        "features": [
            {"title": "Multi-Tier Org Hierarchy", "desc": "Model corporate holding companies, regional subsidiaries, operating divisions, and physical plant locations with parent-child inheritance.", "icon": "building"},
            {"title": "Site & Location Master", "desc": "Standardize building nomenclature, floor plans, production bays, and environmental cleanroom zones across all geographic sites.", "icon": "map-pin"},
            {"title": "Team & Role Assignment", "desc": "Assign maintenance supervisors, reliability engineers, and field technicians to specific facilities with jurisdictional permissions.", "icon": "people"},
            {"title": "Access & Boundary Control", "desc": "Maintain strict tenant and departmental separation with cryptographic audit logging and role-based data visibility.", "icon": "lock"},
        ],
        "deep_dive": {
            "title": "Enterprise Structural Governance",
            "p1": "Modern industrial operations require dynamic, flexible organization models that reflect real-world operational ownership without compromising tenant boundaries. FieldOps Nexus provides a hierarchical data engine that maps physical facilities, logical business units, and authorized contractor scopes.",
            "p2": "Every maintenance schedule, service ticket, and asset lifecycle event inherits jurisdictional boundaries from the location tree, eliminating cross-facility data leakage and ensuring audit-ready compliance.",
        }
    },

    "asset-management": {
        "title": "Asset Management",
        "subtitle": "ENTERPRISE ASSET TRACKING & HIERARCHY",
        "tagline": "Know the condition, history, and location of every critical asset.",
        "description": "Track physical assets across complex enterprise sites, maintain granular parent-child hierarchies, and monitor live operational telemetry with zero blind spots.",
        "image_path": "images/module-assets.jpg",
        "overlay_label": "Live Telemetry & Vibration Analysis Active",
        "metrics": [
            ["2,846", "Active Assets Monitored", "Across 14 enterprise facilities and regional operating plants"],
            ["99.4%", "Asset Registry Integrity", "Continuous barcode verification and automated change audits"],
            ["34%", "Downtime Reduction", "Achieved through proactive condition monitoring and asset genealogy"],
        ],
        "features": [
            {"title": "Parent-Child Hierarchy", "desc": "Build multi-tier asset trees from regional sites down to individual components, assemblies, and sub-assemblies.", "icon": "boxes"},
            {"title": "QR & Barcode Tagging", "desc": "Instant mobile lookup by scanning physical tags on machinery, field hardware, and spare subcomponents.", "icon": "search"},
            {"title": "Telemetry & Logs", "desc": "Real-time vibration, temperature, and operating hours tracking with automated threshold breach alerts.", "icon": "activity"},
            {"title": "Lifecycle & Depreciation", "desc": "Calculate straight-line and accelerated depreciation schedules, track replacement warranties, and budget renewals.", "icon": "trending-up"},
        ],
        "deep_dive": {
            "title": "Continuous Asset Intelligence",
            "p1": "Complex machinery operates in unforgiving conditions. From high-pressure centrifugal pumps to automated robotic assembly arms, FieldOps Nexus captures every sensor pulse, operating hour, and maintenance intervention to build an immutable asset health history.",
            "p2": "Field technicians scanning a physical QR code instantly access complete engineering schematics, bill of materials, warranty entitlement, and historical work orders, reducing diagnostic time by over 40%.",
        }
    },

    "service-management": {
        "title": "Service Management",
        "subtitle": "CUSTOMER INTAKE & SLA TRIAGE",
        "tagline": "Deliver responsive, predictable service from intake to resolution.",
        "description": "Streamline client service requests, enforce strict contractual SLAs, and route tickets intelligently to eliminate operational bottlenecks.",
        "image_path": "images/module-service.jpg",
        "overlay_label": "Dynamic SLA Priority Triage Active",
        "metrics": [
            ["14 min", "Avg. Initial Response", "Automated triage and priority routing across all ticket intake channels"],
            ["98.7%", "Contractual SLA Compliance", "Dynamic timer monitoring with auto-pause during customer holds"],
            ["92%", "First-Touch Resolution Rate", "Equipping intake coordinators with diagnostic trees and asset history"],
        ],
        "features": [
            {"title": "Multi-Channel Intake", "desc": "Ingest service requests via requester portal, email parsing, emergency dispatch hotline, and connected IoT trigger alarms.", "icon": "file-text"},
            {"title": "Dynamic SLA Timers", "desc": "Automated response and resolution clocks calibrated to priority tier, operating hours calendars, and contractual terms.", "icon": "clock"},
            {"title": "Client Portal Access", "desc": "Self-service visibility for internal business units and external clients to log issues, track progress, and approve work.", "icon": "globe"},
            {"title": "First-Time Fix Analytics", "desc": "Identify recurring root causes, measure resolution velocity, and refine triage playbooks based on historical trends.", "icon": "bar-chart"},
        ],
        "deep_dive": {
            "title": "Predictable Service Intake to Resolution",
            "p1": "Field service operations often fail at the intake boundary, where incomplete issue descriptions and manual routing delay urgent interventions. FieldOps Nexus standardizes incident capture with guided symptom trees, automated severity ranking, and immediate SLA clock initiation.",
            "p2": "Once approved, tickets convert cleanly into scheduled work orders with pre-populated parts requirements, technician skill matching, and customer notifications.",
        }
    },

    "work-order-management": {
        "title": "Work Order Management",
        "subtitle": "END-TO-END TASK ORCHESTRATION",
        "tagline": "Plan, assign, and track work orders with absolute clarity.",
        "description": "Equip planners and technicians with clear digital work orders, parts staging, safety checklists, and audit-ready digital signatures.",
        "image_path": "images/module-work-orders.jpg",
        "overlay_label": "Work Order Lifecycle #WO-8820 In Progress",
        "metrics": [
            ["142", "Active Work Orders", "Scheduled across mechanical, electrical, and facility teams"],
            ["4.2 hrs", "Mean Time to Repair (MTTR)", "Optimized through pre-staged parts kits and digital task procedures"],
            ["100%", "Safety Permit Compliance", "Enforced lockout/tagout (LOTO) checklists prior to job commencement"],
        ],
        "features": [
            {"title": "Digital Work Packages", "desc": "Comprehensive task instructions, engineering drawings, required spare parts lists, and specialized tool requirements in one view.", "icon": "clipboard-list"},
            {"title": "Skills-Based Dispatch", "desc": "Intelligent allocation matching job complexity with certified technician qualifications, shift rosters, and travel proximity.", "icon": "user"},
            {"title": "Mobile Execution", "desc": "Field execution interface with offline checklist completion, photo evidence capture, and real-time labor timers.", "icon": "wrench"},
            {"title": "Digital Sign-Off", "desc": "Multi-party verification with customer signatures, supervisor sign-offs, and automated compliance archival.", "icon": "check-circle"},
        ],
        "deep_dive": {
            "title": "Frictionless Field Execution",
            "p1": "Every work order represents an investment of skilled labor and enterprise capital. FieldOps Nexus turns complex job packages into simple, step-by-step mobile workflows that field crews can execute with absolute certainty, even in offline environments.",
            "p2": "Integrated parts reservations ensure replacement components are checked out and ready before dispatch, preventing costly second trips and preserving team momentum.",
        }
    },

    "inventory-management": {
        "title": "Inventory & Spare Parts",
        "subtitle": "MULTI-WAREHOUSE & VAN STOCK CONTROL",
        "tagline": "Keep essential parts moving without overstocking.",
        "description": "Eliminate stockouts and delays with multi-location inventory tracking, automated min/max reordering, and barcode scanning.",
        "image_path": "images/module-inventory.jpg",
        "overlay_label": "Multi-Bin Stock Ledger Verified",
        "metrics": [
            ["$1.2M", "Tracked Parts Value", "Maintained across central warehouses, plant tool cribs, and fleet vans"],
            ["0", "Unscheduled Stockout Delays", "Automated predictive reorder triggers preventing inventory starvation"],
            ["99.8%", "Cycle Count Precision", "Double-entry stock movement ledger with serialized batch traceability"],
        ],
        "features": [
            {"title": "Multi-Site Warehousing", "desc": "Track bin-level stock balances across central regional stores, departmental tool cribs, and mobile technician vehicles.", "icon": "package"},
            {"title": "Automated Reordering", "desc": "Dynamic safety stock calculation, automated purchase order drafts upon threshold breach, and lead-time buffering.", "icon": "refresh-cw"},
            {"title": "Part Reservation", "desc": "Hold critical spares against planned maintenance work orders to guarantee parts availability prior to dispatch.", "icon": "boxes"},
            {"title": "Cycle Counting", "desc": "Streamlined inventory audits with mobile barcode scanners, variance approval workflows, and ledger reconciliations.", "icon": "list-check"},
        ],
        "deep_dive": {
            "title": "High-Velocity Supply Chain Alignment",
            "p1": "Downtime costs spiral when maintenance crews discover required replacement bearings or seals are out of stock. FieldOps Nexus integrates parts management directly into the asset and work order workflows, providing real-time visibility into parts availability.",
            "p2": "Automated reorder triggers calculate historical consumption rates, supplier lead times, and seasonal buffers to optimize cash flow while safeguarding equipment availability.",
        }
    },

    "maintenance-management": {
        "title": "Maintenance Management",
        "subtitle": "PREVENTIVE & PREDICTIVE SCHEDULING",
        "tagline": "Stay ahead of equipment downtime with proactive maintenance.",
        "description": "Automate preventive maintenance schedules, track equipment health degradation, and shift from reactive firefighting to predictive reliability.",
        "image_path": "images/module-maintenance.jpg",
        "overlay_label": "Automated PM Recurrence Calibrated",
        "metrics": [
            ["96.4%", "PM Schedule Compliance", "Proactive work completion within approved maintenance grace windows"],
            ["42%", "Emergency Work Reduction", "Achieved through systematic meter-based and calendar-based servicing"],
            ["1,200+", "PM Plans Executed", "Standardized maintenance sequences across all enterprise rotating assets"],
        ],
        "features": [
            {"title": "Calendar & Meter PMs", "desc": "Trigger preventive maintenance jobs based on elapsed days, machine run hours, production cycles, or seasonal blackout windows.", "icon": "calendar"},
            {"title": "Inspection Checklists", "desc": "Step-by-step Standard Operating Procedures with quantitative measurement thresholds and mandatory photo attachments.", "icon": "clipboard-check"},
            {"title": "Condition Monitoring", "desc": "Ingest vibration, thermal, and oil analysis readings to detect early signs of mechanical degradation before functional failure.", "icon": "activity"},
            {"title": "Compliance Audits", "desc": "Export tamper-evident maintenance histories for OSHA, ISO 55001, EPA, and internal corporate safety governance.", "icon": "shield"},
        ],
        "deep_dive": {
            "title": "From Reactive Repair to Asset Reliability",
            "p1": "Unscheduled breakdowns are the single largest source of unnecessary operational expenditure in modern industrial operations. FieldOps Nexus replaces manual calendar reminders with intelligent recurring maintenance engines that adjust dynamically.",
            "p2": "Condition-based maintenance algorithms monitor operational telemetry such as vibration velocity, bearing temperatures, and pressure differentials, generating proactive work orders before mechanical degradation causes line stoppages.",
        }
    },

    "workforce-management": {
        "title": "Workforce Management",
        "subtitle": "TECHNICIAN DISPATCH & SKILL MATRICES",
        "tagline": "Give every field team member the context to do their best work.",
        "description": "Coordinate technician schedules, track real-time job progression, and empower field teams with intuitive mobile tools.",
        "image_path": "images/module-workforce.jpg",
        "overlay_label": "Technician Fleet Radar Active",
        "metrics": [
            ["88%", "Field Wrench Time", "Minimizing administrative paperwork and transit dead-time through smart dispatch"],
            ["100%", "Certification Tracking", "Enforcing up-to-date electrical, safety, and manufacturer credentials"],
            ["45 min", "Average Dispatch Time", "Rapid mobilization of the nearest qualified specialist for emergency tickets"],
        ],
        "features": [
            {"title": "Skill & Qualification Matrix", "desc": "Maintain verified technician records covering high-voltage certifications, confined space training, and brand-specific expertise.", "icon": "user"},
            {"title": "Live Dispatch Map", "desc": "Visual operational board displaying active jobs, crew locations, shift availability, and regional travel corridors.", "icon": "map-pin"},
            {"title": "Mobile First Design", "desc": "Responsive interface tailored for smartphones and rugged tablets, enabling hands-free voice notes and barcode scanning.", "icon": "wrench"},
            {"title": "Performance Scorecards", "desc": "Objective productivity metrics tracking first-time fix rates, average completion times, and client satisfaction scores.", "icon": "bar-chart"},
        ],
        "deep_dive": {
            "title": "Empowering the People Behind the Operations",
            "p1": "Behind every functioning plant, building, and utility system is a team of dedicated technicians and engineers. FieldOps Nexus is designed from the field upward, removing bureaucratic friction, paper forms, and double-entry so specialists can focus on craftsmanship.",
            "p2": "Automated skill validation prevents assigning tasks to unqualified personnel, protecting worker safety and maintaining insurance compliance across hazardous environments.",
        }
    },

    "analytics-reporting": {
        "title": "Analytics & Reporting",
        "subtitle": "EXECUTIVE OPERATIONAL INTELLIGENCE",
        "tagline": "Turn operational data into confident decisions.",
        "description": "Gain full executive visibility into equipment MTTR, technician utilization, parts spend, and SLA performance across all enterprise locations.",
        "image_path": "images/module-analytics.jpg",
        "overlay_label": "Live KPI Pipeline Streaming",
        "metrics": [
            ["50+", "Standard KPI Metrics", "Covering equipment reliability, labor efficiency, inventory turns, and SLA health"],
            ["Real-Time", "Dashboard Refresh", "Continuous data streaming eliminating delayed end-of-month reporting cycles"],
            ["$420K", "Identified Annual Savings", "Pinpointed through rogue parts consumption and recurring breakdown root causes"],
        ],
        "features": [
            {"title": "MTTR & MTBF Trends", "desc": "Track Mean Time to Repair and Mean Time Between Failures across equipment classes to evaluate reliability investments.", "icon": "trending-up"},
            {"title": "Cost & Budget Analytics", "desc": "Aggregate internal labor hours, contractor invoices, and replacement part expenditures against operating budgets.", "icon": "bar-chart"},
            {"title": "SLA Adherence Reports", "desc": "Detailed breakdown of response time compliance, breach penalties, and department performance rankings.", "icon": "clock"},
            {"title": "Custom BI Exports", "desc": "Automated scheduled exports to Power BI, Snowflake, Tableau, and enterprise data lakes in parquet and CSV formats.", "icon": "database"},
        ],
        "deep_dive": {
            "title": "Operational Intelligence for Clear Decisions",
            "p1": "Industrial enterprises produce millions of operational data points across work orders, telemetry streams, and inventory transactions. FieldOps Nexus transforms this raw operational exhaust into clear, decision-grade executive intelligence.",
            "p2": "Interactive dashboards allow directors to drill down from high-level corporate uptime metrics to individual machine failure modes, identifying capital replacement priorities with quantifiable ROI.",
        }
    },

    "audit-traceability": {
        "title": "Audit & Traceability",
        "subtitle": "OPERATIONAL ACTIVITY & VERIFICATION HISTORY",
        "tagline": "Maintain a complete history of all operational activities.",
        "description": "Maintain clear operational history for internal reviews with digital activity records, photographic attachments, and timestamped supervisor sign-offs.",
        "image_path": "images/audit-traceability.jpg",
        "overlay_label": "Append-Only Immutable Ledger Verified",
        "metrics": [
            ["Immutable", "Append-Only Ledger", "Cryptographic hashing ensuring zero retroactive record manipulation"],
            ["100%", "Action Attribution", "Every state transition, part issuance, and ticket modification tied to user ID"],
            ["Instant", "Compliance Retrieval", "Generate full regulatory audit packets for any asset or work order in seconds"],
        ],
        "features": [
            {"title": "Operational Audit Log", "desc": "Detailed chronological recording of all system events including status changes, parameter edits, and approval steps.", "icon": "lock"},
            {"title": "Digital Signature Capture", "desc": "Touchscreen sign-offs with captured signer names, timestamps, and geolocation tags for verifiable accountability.", "icon": "check-circle"},
            {"title": "Inspection Templates", "desc": "Locked inspection forms requiring mandatory evidence attachments before allow closure or status advancement.", "icon": "clipboard-check"},
            {"title": "Photo & Document Archive", "desc": "Secure cloud vault for site photos, vendor warranties, commissioning certificates, and safety permits.", "icon": "image"},
        ],
        "deep_dive": {
            "title": "Tamper-Evident Governance and Compliance",
            "p1": "When regulatory inspectors, insurance adjusters, or enterprise auditors request proof of maintenance compliance, manual paper binders and fragmented spreadsheets fail. FieldOps Nexus provides an append-only digital ledger of every operational event.",
            "p2": "Cryptographically verified actor signatures, timestamped photo evidence, and calibration certificates are permanently bound to the asset record, providing unassailable compliance documentation.",
        }
    },

    "manufacturing": {
        "title": "Manufacturing Solutions",
        "subtitle": "HEAVY INDUSTRY & PRODUCTION UPTIME",
        "tagline": "Keep production-critical assets and lines running without downtime.",
        "description": "Maintain assembly lines, stamping presses, and robotic cells with precision preventive maintenance schedules and rapid breakdown dispatch.",
        "image_path": "images/left.jpg",
        "overlay_label": "Automated Assembly Line Telemetry Active",
        "metrics": [
            ["45%", "Unscheduled Downtime Reduction", "Achieved through predictive component replacement and proactive PM cycles"],
            ["8.5 min", "Line Stoppage Response", "Instant emergency escalation paging maintenance teams to halted workstations"],
            ["99.2%", "Overall Equipment Effectiveness (OEE)", "Optimized machine availability and production quality throughput"],
        ],
        "features": [
            {"title": "Line Stoppage Alarms", "desc": "Immediate automated alerting when high-speed automated assembly lines experience sensor trips or motor fault stops.", "icon": "bell"},
            {"title": "Tooling & Die Tracking", "desc": "Monitor stroke counts, thermal cycles, and wear patterns on precision dies, molds, and CNC cutting tools.", "icon": "wrench"},
            {"title": "Shift Handover Notes", "desc": "Structured operational logs passed between morning, evening, and night maintenance crews with open issue tracking.", "icon": "file-text"},
            {"title": "Total Productive Maintenance", "desc": "Empower machine operators with daily autonomous cleaning, inspection, and minor lubrication digital checklists.", "icon": "settings"},
        ],
        "deep_dive": {
            "title": "Zero-Unplanned-Downtime Manufacturing",
            "p1": "In high-throughput manufacturing, an unplanned line stoppage can cost tens of thousands of dollars per minute in lost output and scrapped materials. FieldOps Nexus provides an integrated reliability framework purpose-built for industrial production lines.",
            "p2": "By connecting machine PLCs directly with maintenance dispatch rosters, automated alerts mobilize qualified technicians with the exact spare parts and schematics required before small anomalies escalate into major shutdowns.",
        }
    },

    "facilities": {
        "title": "Facilities Management",
        "subtitle": "COMMERCIAL & CORPORATE INFRASTRUCTURE",
        "tagline": "Coordinate spaces, people, and tenant service delivery.",
        "description": "Manage HVAC chillers, elevators, fire suppression systems, and occupant work requests across multi-tenant commercial real estate.",
        "image_path": "images/center.jpg",
        "overlay_label": "Building Automation & Life Safety Active",
        "metrics": [
            ["14M sq ft", "Managed Commercial Space", "Across corporate headquarters, medical centers, and mixed-use complexes"],
            ["99.9%", "Life Safety System Compliance", "Automated testing reminders for fire dampers, sprinklers, and emergency generators"],
            ["18 min", "Tenant Request Resolution", "Self-service submission with real-time technician arrival notifications"],
        ],
        "features": [
            {"title": "Tenant Request Portal", "desc": "Branded web and mobile portal allowing occupants to report temperature, lighting, and plumbing requests effortlessly.", "icon": "building"},
            {"title": "Life Safety & Compliance", "desc": "Automate periodic inspections for fire suppression systems, egress routes, elevators, and air quality standards.", "icon": "shield"},
            {"title": "Vendor & Contractor Control", "desc": "Enforce insurance certificate verification, track vendor access badges, and approve contracted invoices.", "icon": "briefcase"},
            {"title": "Space & Asset Hierarchy", "desc": "Map equipment down to campus, building, floor, suite, and mechanical room for rapid location dispatch.", "icon": "grid"},
        ],
        "deep_dive": {
            "title": "Optimized Multi-Tenant Facility Operations",
            "p1": "Modern commercial facilities are complex ecosystems combining sophisticated mechanical systems, strict safety regulations, and demanding tenant expectations. FieldOps Nexus bridges facility engineering with customer service delivery.",
            "p2": "Automated recurring maintenance schedules protect high-value capital assets like centrifugal chillers, backup diesel generators, and building envelope systems while reducing tenant friction.",
        }
    },

    "service-maintenance": {
        "title": "Service & Maintenance",
        "subtitle": "RESPONSIVE FIELD EXECUTION",
        "tagline": "Deliver responsive service, proactive maintenance execution, and asset reliability wherever work happens.",
        "description": "Bridge the gap between work order intake, technician dispatch, van inventory, and verified completion to minimize operational disruptions.",
        "image_path": "images/right.jpg",
        "overlay_label": "Live Field Service Dispatch Active",
        "metrics": [
            ["Multi-Tier", "SLA Contract Adherence", "Configurable policies across emergency repairs and scheduled servicing"],
            ["Pre-Staged", "First-Time Fix Support", "Linked spare parts staging and mobile digital manuals"],
            ["Tracked", "Incident MTTR Governance", "Automated timer tracking from initial triage to supervisor sign-off"],
        ],
        "features": [
            {"title": "Preventive & Corrective Schedules", "desc": "Automate recurring maintenance tasks based on operating run-hours, sensor telemetry thresholds, or calendar intervals.", "icon": "calendar"},
            {"title": "Skill-Based Dispatching", "desc": "Match service requests with qualified technicians holding the required skills, clearances, and training records.", "icon": "user"},
            {"title": "Mobile Van Stock & Parts Staging", "desc": "Verify spare parts availability in the technician's vehicle before dispatch to prevent unnecessary second visits.", "icon": "package"},
            {"title": "Digital Sign-Off & Verification", "desc": "Capture touchscreen customer sign-offs, before-and-after work photos, and GPS-stamped completion receipts.", "icon": "check-circle"},
        ],
        "deep_dive": {
            "title": "Precision Field Dispatch and Execution",
            "p1": "When distributed equipment requires physical servicing, coordination errors between dispatchers, field technicians, and warehouse stock controllers multiply costs and delay repairs. FieldOps Nexus creates a unified operational thread connecting every stakeholder.",
            "p2": "Technicians arriving on site have verified parts kits, digital schematics, step-by-step Standard Operating Procedures, and instant access to past machine logs right on their mobile devices.",
        }
    },

    "infrastructure": {
        "title": "Infrastructure & Utilities",
        "subtitle": "MISSION-CRITICAL PUBLIC ASSETS",
        "tagline": "Maintain the systems and assets that communities and enterprises depend on.",
        "description": "Ensure continuous reliability, regulatory compliance, and rapid incident response across power grids, municipal water facilities, transportation networks, and critical utilities.",
        "image_path": "images/fieldops-workflow-visual.jpg",
        "overlay_label": "Continuous 24/7 Grid & Station Uptime Active",
        "metrics": [
            ["24/7/365", "Continuous Uptime Monitoring", "Automated telemetry alerts for electrical substations and pump stations"],
            ["Structured", "Safety & Inspection Governance", "Digital inspection checklists and structured logging for equipment audits"],
            ["Rapid", "Emergency Dispatch Coordination", "Configurable crew mobilization during severe weather and utility events"],
        ],
        "features": [
            {"title": "Grid & Facility Reliability", "desc": "Monitor transformer temperatures, flow rates, and pipeline pressure with automated SCADA alarms.", "icon": "activity"},
            {"title": "High-Compliance Inspections", "desc": "Enforce environmental protection protocols, EPA standards, and safety sign-offs with tamper-evident digital records.", "icon": "shield"},
            {"title": "Distributed Asset Mapping", "desc": "Geospatial visualization of pump stations, substations, and fiber trunks across geographic districts.", "icon": "map-pin"},
            {"title": "Severe Weather Protocols", "desc": "Instantly mobilize standby field crews and triage regional outages with priority restoration sequences.", "icon": "alert-triangle"},
        ],
        "deep_dive": {
            "title": "Resilient Public Infrastructure Management",
            "p1": "Critical municipal and utility infrastructure operates under strict environmental mandates, safety oversight, and extreme weather risks. FieldOps Nexus supports geographically distributed teams maintaining assets spanning thousands of square miles.",
            "p2": "Mobile field inspection records operate reliably even in dead zones, automatically syncing back to central command when connectivity is reestablished.",
        }
    },

    "enterprise-operations": {
        "title": "Enterprise Operations",
        "subtitle": "SCALABLE MULTI-SITE INFRASTRUCTURE",
        "tagline": "Unify complex operations across your organization.",
        "description": "Standardize field operations across multi-country facilities with unified data governance, consolidated inventory, and executive dashboards.",
        "image_path": "images/operational-visibility.jpg",
        "overlay_label": "Enterprise Multi-Site Operations Console",
        "metrics": [
            ["48+", "Global Operating Sites", "Unified under standardized maintenance workflows and master data models"],
            ["30%", "Overhead Administration Reduction", "Eliminating redundant regional software silos and manual reconciliations"],
            ["SOC 2", "Type II Certified Governance", "Enterprise-grade encryption, tenant isolation, and automated compliance logging"],
        ],
        "features": [
            {"title": "Multi-Entity Architecture", "desc": "Support multi-company structures with separate chart of accounts, regional currencies, and local tax compliance.", "icon": "building"},
            {"title": "Custom Integrations", "desc": "Bi-directional real-time connectors for SAP, Oracle NetSuite, Microsoft Dynamics 365, and SCADA historians.", "icon": "layers"},
            {"title": "Enterprise SLA Management", "desc": "Manage cross-regional service contracts with tiered response commitments, escalation ladders, and breach tracking.", "icon": "clock"},
            {"title": "Security & Governance", "desc": "Single Sign-On (SAML/Okta/Azure AD), granular role-based permissions, and immutable audit logging across all entities.", "icon": "lock"},
        ],
        "deep_dive": {
            "title": "Global Consistency with Regional Flexibility",
            "p1": "Enterprise organizations frequently struggle with fragmented regional software instances, divergent maintenance naming conventions, and inconsistent SLA compliance reporting. FieldOps Nexus provides a single source of truth across all enterprise entities.",
            "p2": "Corporate reliability executives can compare plant performance, benchmark contractor rates, and balance inventory across regional clusters with real-time accuracy.",
        }
    },

    "sla-management": {
        "title": "SLA Management",
        "subtitle": "SERVICE-LEVEL OBLIGATIONS & COMPLIANCE",
        "tagline": "Enforce commitments, eliminate response bottlenecks, and maintain audit-ready visibility.",
        "description": "Monitor service-level commitments, track response and resolution performance, and maintain visibility into operational service obligations.",
        "image_path": "images/workflow-approval.jpg",
        "overlay_label": "Active SLA Countdown Timers Monitored",
        "metrics": [
            ["99.4%", "Target SLA Adherence", "Real-time countdown clocks highlighting at-risk tickets before breach occurs"],
            ["4 Tiers", "Priority Escalation Matrix", "P1 Critical (15 min) through P4 Routine (48 hr) calibrated response policies"],
            ["100%", "Contractual Pause Tracking", "Verifiable clock pauses during customer pending states and spare part shipping"],
        ],
        "features": [
            {"title": "Tiered SLA Policies", "desc": "Configure custom response and resolution windows based on customer contract, equipment tier, and geographic zone.", "icon": "speedometer2"},
            {"title": "Automated Clock Pauses", "desc": "Legitimate clock pauses when waiting for tenant site access, third-party permits, or parts delivery with audit proof.", "icon": "pause"},
            {"title": "Predictive Breach Alerts", "desc": "Visual warning flags and mobile push notifications when tickets reach 75% and 90% of allowed resolution windows.", "icon": "alert-triangle"},
            {"title": "Service Reports", "desc": "Export monthly client SLA scorecards detailing response times, fix rates, and contract compliance credits.", "icon": "file-text"},
        ],
        "deep_dive": {
            "title": "Guaranteed Service-Level Governance",
            "p1": "Contractual service penalties and reputational damage mount rapidly when client tickets slip through administrative gaps. FieldOps Nexus embeds SLA countdown clocks directly into every view across dispatch boards, technician screens, and management dashboards.",
            "p2": "Automated pause controls record exact timestamps and reasons when work is suspended due to client holds or supplier lead times, ensuring fair, transparent compliance audits.",
        }
    },

    "multi-site-management": {
        "title": "Multi-Site Management",
        "subtitle": "DISTRIBUTED OPERATIONS & FACILITY GOVERNANCE",
        "tagline": "Bring sites, teams, assets, and service operations into one connected operational view.",
        "description": "Coordinate multi-facility portfolios with global standards, shared resource pools, and centralized visibility into asset health and maintenance compliance.",
        "image_path": "images/module-organization.jpg",
        "overlay_label": "Cross-Site Resource Coordination Active",
        "metrics": [
            ["60+", "Managed Operating Facilities", "Industrial plants, commercial distribution hubs, and service campuses"],
            ["Cross-Site", "Parts Pooling & Visibility", "Search neighboring warehouses before ordering expensive emergency replacements"],
            ["Single Pane", "Fleet Operations Visibility", "Roll-up views of facility uptime, open work orders, and safety audit status"],
        ],
        "features": [
            {"title": "Location Master Registry", "desc": "Maintain standardized global site directories with geofenced boundaries, contact rosters, and operational hours.", "icon": "map-pin"},
            {"title": "Building & Bay Mapping", "desc": "Drill down from regional maps into specific plant buildings, production bays, and floor-level room layouts.", "icon": "building"},
            {"title": "Fleet Radar Console", "desc": "Real-time interactive dashboard monitoring active jobs, urgent alerts, and resource availability across all locations.", "icon": "activity"},
            {"title": "Cross-Site Workforce", "desc": "Temporarily deploy specialist technicians across regional plant clusters to cover surge workloads and turnarounds.", "icon": "people"},
        ],
        "deep_dive": {
            "title": "Centralized Governance with Local Autonomy",
            "p1": "Managing distributed facilities requires striking the right balance between corporate standardization and on-the-ground operational agility. FieldOps Nexus allows plant managers to control local schedules while providing executive leaders with unified portfolio metrics.",
            "p2": "Shared spare parts catalogs allow facilities within the same geographical cluster to borrow high-value safety stock during emergencies, reducing emergency freight charges and downtime.",
        }
    },

    "connected-data": {
        "title": "Connected Data",
        "subtitle": "UNIFIED SERVICE & OPERATIONAL INFORMATION",
        "tagline": "Connect operational information across teams, locations, assets, service requests, and work orders to support a consistent view of service operations.",
        "description": "Eliminate operational blind spots by linking every asset telemetry reading, customer service request, work order checklist, and inventory part into a unified relational data model.",
        "image_path": "images/connected-data.jpg",
        "overlay_label": "Relational Operational Graph Synced",
        "metrics": [
            ["0 Silos", "Unified Operational Schema", "Assets, requests, work orders, and spare parts fully integrated"],
            ["Connected", "Lifecycle Traceability", "From initial intake and diagnostic telemetry to verified customer sign-off"],
            ["Direct", "Information Lookup", "Complete equipment historical records accessible in milliseconds in the field"],
        ],
        "features": [
            {"title": "Relational Operational Graph", "desc": "Every work order and replacement part directly links back to the parent asset genealogy and operating history.", "icon": "database"},
            {"title": "Zero Double-Entry", "desc": "Technician diagnostic notes flow seamlessly from intake ticket into active work order and final invoice receipt.", "icon": "refresh-cw"},
            {"title": "Mobile Pedigree Access", "desc": "Technicians scan physical machinery QR codes for instant offline access to manuals, schematics, and prior work orders.", "icon": "search"},
            {"title": "Operational Audit Trail", "desc": "Structured change logs with microsecond timestamps and cryptographically verifiable actor tracking.", "icon": "lock"},
        ],
        "deep_dive": {
            "title": "The End of Operational Data Fragmentation",
            "p1": "Traditional maintenance setups trap vital intelligence inside isolated silos: work orders in one app, sensor data in another, parts inventory in an ERP, and customer communications in email threads. FieldOps Nexus unifies them into a single interconnected operational graph.",
            "p2": "When a technician views an asset record, they see its entire life story: past breakdowns, replacement components, calibration logs, and telemetry trends, enabling rapid, root-cause diagnosis.",
        }
    },

    "inspection-checklist": {
        "title": "Inspection & Checklist",
        "subtitle": "QUALITY ASSURANCE & SAFETY COMPLIANCE",
        "tagline": "Standardize field inspections and ensure regulatory compliance with digital SOPs.",
        "description": "Deploy dynamic inspection templates, enforce mandatory safety verification gates, and log corrective findings with photo documentation and digital sign-offs.",
        "image_path": "images/workflow-field-operations.jpg",
        "overlay_label": "Dynamic SOP & LOTO Safety Gates Active",
        "metrics": [
            ["100%", "Safety Gate Enforcement", "Technicians cannot advance work without completing mandatory PPE and hazard checklists"],
            ["350+", "Standardized Inspection SOPs", "Pre-configured templates covering OSHA, electrical, mechanical, and pressure vessel audits"],
            ["Zero", "Missing Inspection Records", "Automated cloud synchronization with tamper-evident audit archival"],
        ],
        "features": [
            {"title": "Dynamic Inspection Checklists", "desc": "Build conditional checklists with pass/fail criteria, numeric tolerance ranges, and mandatory photo verification.", "icon": "list-check"},
            {"title": "Corrective Finding Workflows", "desc": "Failed inspection items automatically generate follow-up corrective work orders with priority triage.", "icon": "alert-triangle"},
            {"title": "Safety & Permit Verification", "desc": "Enforce Hot Work Permits, Lockout/Tagout (LOTO), and Confined Space sign-offs before job start.", "icon": "shield"},
            {"title": "Compliance Reporting", "desc": "Generate one-click inspection certificates for ISO, OSHA, and insurance underwriters.", "icon": "clipboard-check"},
        ],
        "deep_dive": {
            "title": "Defensible Safety and Quality Audits",
            "p1": "Paper inspection sheets are prone to skipped items, illegible handwriting, and lost records. FieldOps Nexus enforces rigorous digital Standard Operating Procedures that guide technicians through every inspection step.",
            "p2": "When an inspector flags an out-of-spec measurement, the system automatically prompts for photographic evidence and initiates an immediate corrective work order, preventing hazardous conditions from persisting unaddressed.",
        }
    },

    "contracts-warranty": {
        "title": "Warranty / AMC / Contract",
        "subtitle": "COMMERCIAL ENTITLEMENTS & VENDOR AGREEMENTS",
        "tagline": "Protect service entitlements and avoid paying for covered repairs.",
        "description": "Track vendor agreements, verify active warranty coverage before ordering replacement parts, manage preventive maintenance service contracts, and receive timely expiration alerts.",
        "image_path": "images/workflow-approval.jpg",
        "overlay_label": "Warranty Coverage & SLA Entitlement Active",
        "metrics": [
            ["$310K", "Annual Warranty Recovery", "Saved by automatically identifying covered equipment before paying third-party repairs"],
            ["100%", "Contract Entitlement Accuracy", "Automated verification against active service agreements during work order triage"],
            ["60 Days", "Advance Renewal Notices", "Proactive alerting to renegotiate favorable maintenance contracts before expiration"],
        ],
        "features": [
            {"title": "Warranty Coverage Verification", "desc": "Instantly check whether failed assets or replacement components are under manufacturer or contractor warranty.", "icon": "shield"},
            {"title": "Annual Maintenance Contracts (AMC)", "desc": "Define recurring vendor visit schedules, billing milestones, and service level agreements.", "icon": "briefcase"},
            {"title": "Vendor Performance Tracking", "desc": "Evaluate external maintenance providers based on contract SLA response times and repair quality.", "icon": "bar-chart"},
            {"title": "Entitlement Clamping", "desc": "Prevent out-of-scope work order execution without required supervisor authorization or contract amendments.", "icon": "lock"},
        ],
        "deep_dive": {
            "title": "Automated Commercial Safeguards",
            "p1": "Industrial enterprises routinely spend hundreds of thousands of dollars each year repairing equipment that is actively covered under manufacturer warranty or third-party service agreements. FieldOps Nexus checks warranty status the moment a service request is generated.",
            "p2": "Technicians and planners are immediately alerted to covered components, prompting warranty claims and return authorizations directly from the work order screen.",
        }
    },

    "qr-identification": {
        "title": "QR / Barcode Identification",
        "subtitle": "RAPID MOBILE ASSET TAGGING & DISPATCH",
        "tagline": "Bridge physical assets with digital records in one second.",
        "description": "Generate industrial barcode and QR labels, scan assets with any smartphone camera in the field, and instantly retrieve maintenance histories and submit work orders.",
        "image_path": "images/module-assets.jpg",
        "overlay_label": "High-Speed Optical Scanner Active",
        "metrics": [
            ["1 sec", "Mobile Asset Scan Time", "Instant asset card retrieval using standard smartphone and tablet cameras"],
            ["100%", "Error-Free Identification", "Eliminating manual equipment number entry errors and serial typos"],
            ["Industrial", "Durable Label Formatting", "Direct export for thermal barcode and rugged QR label printers"],
        ],
        "features": [
            {"title": "Barcode & QR Label Generation", "desc": "Batch create standardized asset tags with QR codes, Code 128 barcodes, and human-readable identifiers.", "icon": "search"},
            {"title": "Instant Camera Scanner", "desc": "Built-in browser scanner works seamlessly on iOS, Android, and ruggedized warehouse hand-terminals.", "icon": "camera"},
            {"title": "One-Tap Ticket Submission", "desc": "Field workers scan machinery tags to immediately open pre-populated breakdown service tickets.", "icon": "plus"},
            {"title": "Asset Verification Audits", "desc": "Perform rapid physical inventory checks by scanning tags along plant corridors and mechanical rooms.", "icon": "list-check"},
        ],
        "deep_dive": {
            "title": "Instant Physical-to-Digital Connectivity",
            "p1": "Searching for equipment by typing lengthy serial numbers or confusing asset tags into a keyboard leads to transcription errors and wasted time. FieldOps Nexus turns every mobile device into a high-speed optical barcode scanner.",
            "p2": "When a technician points their camera at an asset label, the application immediately surfaces operational run-hours, recent maintenance work orders, safety warnings, and pending service tickets.",
        }
    },

    "client-portal": {
        "title": "Client / Requester Portal",
        "subtitle": "SELF-SERVICE INTAKE & REAL-TIME VISIBILITY",
        "tagline": "Provide clients and internal stakeholders with crystal-clear service tracking.",
        "description": "Multi-tenant self-service portal empowering customers and departmental requesters to submit tickets, track real-time technician progress, and approve completed work.",
        "image_path": "images/smarter-workflows.jpg",
        "overlay_label": "Client Portal Self-Service Verified",
        "metrics": [
            ["70%", "Fewer Status Inquiry Calls", "Tenants track live ticket progress directly on mobile and web dashboards"],
            ["4.9 / 5.0", "Requester Satisfaction Rating", "Transparent communication, technician ETA notifications, and easy sign-offs"],
            ["Multi-Tenant", "Data Isolation", "Each organization only sees their dedicated sites, equipment, and tickets"],
        ],
        "features": [
            {"title": "Self-Service Request Submission", "desc": "Intuitive request forms with photo upload, location pickers, and urgency selection.", "icon": "file-text"},
            {"title": "Real-Time Progress Tracker", "desc": "Live status milestones showing Submitted, Triaged, Dispatched, In-Progress, and Completed.", "icon": "clock"},
            {"title": "Work Approval & Sign-Off", "desc": "Review technician completion notes, view after-service photos, and approve job closure digitally.", "icon": "check-circle"},
            {"title": "Role-Based Access for Clients", "desc": "Multi-user access with billing contact, site supervisor, and general employee permission levels.", "icon": "people"},
        ],
        "deep_dive": {
            "title": "Transparent Customer Service Collaboration",
            "p1": "When service requesters lack visibility into repair progress, dispatch phone lines become jammed with status inquiries. FieldOps Nexus offers a dedicated, tenant-isolated self-service portal that keeps clients informed at every stage.",
            "p2": "Automated email and SMS notifications alert users when a technician is en route, when parts are on order, and when work is ready for final sign-off.",
        }
    },

    "technician-workspace": {
        "title": "Technician Workspace",
        "subtitle": "FIELD MOBILITY & JOB EXECUTION CONSOLE",
        "tagline": "Everything the field technician needs to get the job done right the first time.",
        "description": "Purpose-built field mobility workspace providing technicians with digital checklists, spare parts lookup, labor timers, equipment manuals, and offline capability.",
        "image_path": "images/workflow-field-operations.jpg",
        "overlay_label": "Technician Mobile Workspace Connected",
        "metrics": [
            ["Offline", "First Architecture", "Work without interruption in basement plant rooms and remote utility sites"],
            ["1-Click", "Part Deduction", "Deduct used components directly from van stock into the work order ledger"],
            ["Voice-to-Text", "Diagnostic Notes", "Hands-free voice transcription enabling rapid, detailed work descriptions"],
        ],
        "features": [
            {"title": "My Jobs & Daily Schedule", "desc": "Prioritized work order queue sorted by urgency, route optimization, and appointment windows.", "icon": "clipboard-list"},
            {"title": "Active Job Execution", "desc": "Step-by-step checklist items, required measurement inputs, and safety permit sign-offs.", "icon": "wrench"},
            {"title": "Parts & Van Stock Usage", "desc": "Search mobile inventory, log used items, and request central replenishment directly from the field.", "icon": "package"},
            {"title": "Customer Touchscreen Sign-Off", "desc": "Capture customer verification signatures and generate automated completion receipts instantly.", "icon": "check-circle"},
        ],
        "deep_dive": {
            "title": "Engineered for Tough Field Environments",
            "p1": "Field technicians frequently work in basement mechanical rooms, remote rural substations, and shielded industrial facilities where cellular reception is unavailable. The Technician Workspace operates in an offline-first architecture.",
            "p2": "All work order documentation, inspection steps, and photographic proof are saved securely on the local device and automatically synchronized as soon as connectivity resumes.",
        }
    },

    "asset-hierarchy": {
        "title": "Asset Hierarchy",
        "subtitle": "EQUIPMENT GENEALOGY & COMPONENT RELATIONSHIPS",
        "tagline": "Visualize complex equipment relationships from site level down to individual parts.",
        "description": "Build multi-tier asset trees, track parent-child equipment dependencies, maintain serial number component swaps, and analyze failure propagation.",
        "image_path": "images/workflow-asset-management.jpg",
        "overlay_label": "Multi-Tier Tree Lineage Active",
        "metrics": [
            ["7+ Tiers", "Deep Hierarchy Modeling", "Site > Building > System > Machine > Subassembly > Component > Part"],
            ["100%", "Component Genealogy", "Full replacement history tracing swapped pumps, motors, and electronic boards"],
            ["Root Cause", "Propagation Tracking", "Trace component failures back to parent machinery and related subsystems"],
        ],
        "features": [
            {"title": "Visual Asset Trees", "desc": "Interactive graphical tree navigation showing functional equipment relationships and locations.", "icon": "boxes"},
            {"title": "Component Swap History", "desc": "Maintain complete lineage when high-value components are refurbished, swapped, or moved.", "icon": "refresh-cw"},
            {"title": "Cascading Maintenance", "desc": "Schedule parent machine shutdowns while coordinating simultaneous component-level servicing.", "icon": "calendar"},
            {"title": "Failure Impact Analysis", "desc": "Determine downstream operational impact when any single critical asset in the tree fails.", "icon": "alert-triangle"},
        ],
        "deep_dive": {
            "title": "Granular Multi-Tier Asset Genealogy",
            "p1": "Industrial equipment rarely operates in isolation; it functions within interdependent mechanical and electrical systems. FieldOps Nexus allows engineering teams to construct detailed parent-child equipment trees.",
            "p2": "When a subcomponent like an electric drive motor or gearbox is serviced or replaced, its full historical pedigree remains attached to the component record even if swapped into a different parent machine.",
        }
    },
}


PRODUCT_SLUGS = {
    "asset-management",
    "service-management",
    "work-order-management",
    "inventory-management",
    "maintenance-management",
    "workforce-management",
    "analytics-reporting",
    "audit-traceability",
}

SOLUTIONS_SLUGS = {
    "manufacturing",
    "facilities",
    "service-maintenance",
    "infrastructure",
    "enterprise-operations",
    "sla-management",
    "multi-site-management",
    "connected-data",
}

MODULE_SLUGS = {
    "organization-management",
    "asset-management",
    "work-order-management",
    "service-management",
    "inventory-management",
    "maintenance-management",
    "workforce-management",
    "analytics-reporting",
    "audit-traceability",
    "inspection-checklist",
    "contracts-warranty",
    "sla-management",
    "qr-identification",
    "client-portal",
    "technician-workspace",
    "asset-hierarchy",
}

PRD_ID_MAP = {
    "fon-m01": "organization-management",
    "fon-m02": "asset-management",
    "fon-m03": "asset-hierarchy",
    "fon-m04": "maintenance-management",
    "fon-m05": "service-management",
    "fon-m06": "work-order-management",
    "fon-m07": "technician-workspace",
    "fon-m08": "inspection-checklist",
    "fon-m09": "inventory-management",
    "fon-m10": "contracts-warranty",
    "fon-m11": "sla-management",
    "fon-m12": "qr-identification",
    "fon-m13": "client-portal",
    "fon-m14": "analytics-reporting",
    "fon-m15": "audit-traceability",
}

SOLUTIONS_ALIAS_MAP = {
    "maintenance-management": "service-maintenance",
    "maintenance": "service-maintenance",
    "service": "service-maintenance",
    "operations": "enterprise-operations",
    "multisite": "multi-site-management",
}

def get_catalog_item(category, slug):
    """Retrieve validated catalog item for a given category. Returns None if invalid."""
    slug_clean = slug.strip().lower()
    if category == "product":
        if slug_clean in PRODUCT_SLUGS:
            return DETAIL_PAGES.get(slug_clean)
        return None
    elif category == "solutions":
        if slug_clean in SOLUTIONS_SLUGS:
            return DETAIL_PAGES.get(slug_clean)
        mapped = SOLUTIONS_ALIAS_MAP.get(slug_clean)
        if mapped and mapped in DETAIL_PAGES:
            return DETAIL_PAGES.get(mapped)
        return None
    elif category == "modules":
        if slug_clean in MODULE_SLUGS:
            return DETAIL_PAGES.get(slug_clean)
        mapped = PRD_ID_MAP.get(slug_clean)
        if mapped and mapped in DETAIL_PAGES:
            return DETAIL_PAGES.get(mapped)
        return None
    return DETAIL_PAGES.get(slug_clean)


