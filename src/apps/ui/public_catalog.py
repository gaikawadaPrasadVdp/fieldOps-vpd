"""
FieldOps Nexus — Public Marketing and Product Catalog
Provides rich metadata, capability cards, metrics, and photography mappings
for Product, Solutions, and Modules detail pages.
"""

DETAIL_PAGES = {
    "platform-overview": {
        "title": "Platform Overview",
        "subtitle": "ENTERPRISE OPERATIONS PLATFORM",
        "tagline": "Explore the complete FieldOps Nexus enterprise platform.",
        "description": "Unified, end-to-end operational visibility connecting service intake, asset management, automated scheduling, inventory control, and executive analytics into one seamless platform.",
        "image_path": "images/operational-visibility.webp",
        "overlay_label": "FieldOps Nexus Enterprise Architecture Active",
        "metrics": [
            ["100%", "Operational Connectivity", "Single source of truth uniting dispatch, assets, inventory, and field personnel"],
            ["60%", "Resolution Acceleration", "Streamlined triage, automatic routing, and technician workspace empowerment"],
            ["SOC 2", "Certified Reliability", "Enterprise multi-site security, role-based governance, and immutable audit logs"],
        ],
        "features": [
            {"title": "Unified Service Lifecycle", "desc": "From incident notification and customer intake to verified field sign-off and billing handover.", "icon": "activity"},
            {"title": "Asset & Telemetry Grid", "desc": "Continuous condition monitoring, parent-child component trees, and predictive downtime prevention.", "icon": "boxes"},
            {"title": "Intelligent Dispatch Engine", "desc": "Rule-based work order routing factoring technician location, skillset, certifications, and vehicle stock.", "icon": "calendar"},
            {"title": "Executive Control Room", "desc": "Live SLA compliance radars, asset uptime heatmaps, and multi-facility operational analytics.", "icon": "bar-chart"},
        ],
        "deep_dive": {
            "title": "Enterprise-Wide Operational Alignment",
            "p1": "Traditional industrial and service enterprises suffer from disjointed point solutions where technicians, planners, and management view conflicting operational truths. FieldOps Nexus unifies these perspectives into a single resilient system.",
            "p2": "Built for high-tempo industrial, commercial, and utility infrastructure, every status update, telemetry reading, and approval event propagates in real time across the complete operational chain.",
        }
    },
    "core-capabilities": {
        "title": "Core Capabilities",
        "subtitle": "CONNECTED OPERATIONS ENGINE",
        "tagline": "Discover the essential tools for connected operations.",
        "description": "High-velocity field execution tools engineered for reliability, accuracy, and operational excellence across modern industrial and enterprise facilities.",
        "image_path": "images/fieldops-workflow-visual.webp",
        "overlay_label": "FieldOps Nexus Core Capabilities Active",
        "metrics": [
            ["8-Stage", "Service Flow Orchestration", "Standardized process execution from initial triage to verified supervisor closure"],
            ["Zero", "Data Desynchronization", "Instant propagation across mobile technician devices, supervisor consoles, and customer portals"],
            ["99.9%", "Platform High Availability", "Mission-critical system uptime ensuring uninterrupted field operations round-the-clock"],
        ],
        "features": [
            {"title": "End-to-End Orchestration", "desc": "Coordinated workflows linking work order generation, parts reservation, and dispatch scheduling.", "icon": "clipboard-list"},
            {"title": "Mobile Field Mobility", "desc": "Offline-capable technician interface with digital inspection checklists and QR scanning.", "icon": "smartphone"},
            {"title": "Inventory & Ledger Control", "desc": "Multi-warehouse part balancing with automated replenishment and consumption logging.", "icon": "package"},
            {"title": "Audit & Traceability", "desc": "Immutable cryptographic event histories ensuring comprehensive regulatory compliance.", "icon": "lock"},
        ],
        "deep_dive": {
            "title": "Built for High-Stakes Operations",
            "p1": "FieldOps Nexus combines flexible operational modeling with rigorous governance controls. Field teams gain the agility to execute work safely while executives maintain complete oversight of costs, quality, and SLA commitments.",
            "p2": "Automated escalation ladders, multi-tier approval gates, and integrated parts tracking ensure that no service ticket or work order stalls without administrative visibility.",
        }
    },
    "enterprise-architecture": {
        "title": "Enterprise Architecture",
        "subtitle": "SCALABLE SYSTEMS & INTEGRATION ARCHITECTURE",
        "tagline": "Understand the platform architecture and system integration.",
        "description": "Enterprise-grade multi-tenant foundation designed for seamless integration with legacy ERPs, SCADA telemetry, and mission-critical enterprise ecosystems.",
        "image_path": "images/connected-data.webp",
        "overlay_label": "Enterprise Multi-Site Architecture Active",
        "metrics": [
            ["REST & Webhooks", "Open Integration API", "Bi-directional connectors for SAP, Oracle, NetSuite, SCADA, and IoT sensors"],
            ["Multi-Tenant", "Hierarchical Isolation", "Granular organization structures, regional subsidiaries, and isolated plant jurisdictions"],
            ["Sub-Second", "Event Synchronization", "High-throughput operational messaging delivering low-latency field telemetry"],
        ],
        "features": [
            {"title": "Multi-Tier Org Hierarchy", "desc": "Model holding companies, operating divisions, and physical plant locations with granular inheritance.", "icon": "building"},
            {"title": "Bi-Directional ERP Connectors", "desc": "Seamless sync of purchase orders, vendor invoices, asset registries, and inventory levels.", "icon": "cpu"},
            {"title": "Role-Based Security & SSO", "desc": "SAML 2.0 / OAuth2 authentication with fine-grained access control boundaries and audit enforcement.", "icon": "shield-check"},
            {"title": "Edge Telemetry Ingestion", "desc": "Direct connector framework for IoT gateways, vibration monitors, and PLC hardware historians.", "icon": "activity"},
        ],
        "deep_dive": {
            "title": "Interoperable, Scalable Infrastructure",
            "p1": "FieldOps Nexus is architected from the ground up for modern enterprise IT landscapes. Its modular services decouple data capture from workflow business logic, allowing frictionless integration into existing digital ecosystems.",
            "p2": "Whether connecting to on-premise industrial SCADA networks or cloud ERP platforms, FieldOps Nexus ensures secure, encrypted, and audit-ready data flow across all boundary lines.",
        }
    },
    "integrations": {
        "title": "Integrations",
        "subtitle": "CONNECTED ENTERPRISE ECOSYSTEM",
        "tagline": "Connect operational systems and enterprise applications.",
        "description": "Bridge field operations with corporate IT, supply chain ERPs, and facility IoT networks through resilient, high-performance connectors and webhooks.",
        "image_path": "images/connected-data.webp",
        "overlay_label": "Integration Hub & Webhook Gateway Active",
        "metrics": [
            ["50+", "Pre-Built Connectors", "Turnkey integrations for leading ERP, CRM, IoT, and supply chain software solutions"],
            ["100%", "Audit Traceability", "Complete payload logging, replay capabilities, and end-to-end cryptographic verification"],
            ["Real-Time", "Webhook Event Bus", "Sub-second event dispatching to external microservices and automated messaging systems"],
        ],
        "features": [
            {"title": "ERP & Financial Sync", "desc": "Keep general ledgers, asset capitalization, and contractor purchase orders synchronized with SAP and NetSuite.", "icon": "database"},
            {"title": "SCADA & IoT Telemetry", "desc": "Ingest live operational hours, temperature readings, and cycle counts directly from equipment sensors.", "icon": "cpu"},
            {"title": "Customer CRM & Helpdesk", "desc": "Connect incoming support tickets from Salesforce and Zendesk directly into dispatch triage queues.", "icon": "users"},
            {"title": "Custom Webhook Web", "desc": "Build bespoke automated workflows with secure payload signing and automatic retry logic.", "icon": "git-branch"},
        ],
        "deep_dive": {
            "title": "Unbroken Operational Flow Between Systems",
            "p1": "Data silos cause delayed work orders, inaccurate inventory balances, and compliance risks. FieldOps Nexus acts as the central operational exchange between field technicians and enterprise back-office applications.",
            "p2": "Our robust webhook gateway and REST API enable IT teams to extend and customize operational flows without modifying core application code, safeguarding system stability and upgrade paths.",
        }
    },
    "organization-management": {
        "title": "Organization Management",
        "subtitle": "ENTERPRISE HIERARCHY & SITE CONFIGURATION",
        "tagline": "Bring sites, teams, zones, and business units into one connected view.",
        "description": "Define and manage your entire organizational structure — from enterprise groups and regional divisions down to individual sites, departments, and teams. Control access boundaries, asset ownership, and workforce allocation with precision.",
        "image_path": "images/module-organization.webp",
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
        "tagline": "Be able to know the current state, history, and where  abouts of all vital assets.",
        "description": "Track physical assets across complex enterprise sites, maintain detailed parent-child hierarchies, and gain real-time visibility into asset performance and operational conditions.",
        "image_path": "images/module-assets.webp",
        "overlay_label": "Live Telemetry & Vibration Analysis Active",
        "metrics": [
            ["2,846", "Active Assets Tracked", "On 14 enterprise locations and regional plant operations"],
            ["99.4%", "Asset Inventory Accuracy", "Through continuous barcode validation and automated audit changes"],
            ["34%", "Reduced Downtime", "From condition monitoring and asset lineage"],
        ],
        "features": [
            {"title": "Parent-Child Hierarchy", "desc": "Create multi-level asset hierarchies down from the regional site to component level assemblies and sub-assemblies.", "icon": "boxes"},
            {"title": "QR & Barcode Tagging", "desc": "Quick mobile lookup by scanning physical tags on machinery, field equipment, and spare subcomponents.", "icon": "search"},
            {"title": "Telemetry & Logs", "desc": "Real-time vibration, temperature and operating hours tracking with automated threshold violation alerting.", "icon": "activity"},
            {"title": "Lifecycle & Depreciation", "desc": "Compute straight-line and accelerated depreciation schedules and monitor replacement warranties and future budget needs.", "icon": "trending-up"},
        ],
        "deep_dive": {
            "title": "Continuous Asset Intelligence",
            "p1": "Heavy machinery operates under harsh conditions. From highly pressurized centrifugal pumps to robotic arm automated assembly systems, FieldOps Nexus captures each sensor tick, operating hour, and intervention to create an immutable asset lineage.",
            "p2": "A field technician scanning a physical QR code has access to all relevant engineering schematic diagrams, bill of materials, warranties and historical work orders - reducing diagnostic effort by more than 40%.",
        },
        "runtime_configs": [
            {
                "title": "Data Security & Tenant Isolation",
                "desc": "Row-level security with isolated tenant cryptographic keys",
                "status": "Enforced",
            },
            {
                "title": "Mobile Field Accessibility",
                "desc": "Offline-first local data cache with delta sync after reconnecting",
                "status": "Active",
            },
            {
                "title": "Regulatory Audit Ledger",
                "desc": "Append-only log of every actor, timestamp and IP change",
                "status": "Verified",
            },
        ],
    },

    "service-management": {
        "title": "Service Management",
        "subtitle": "CUSTOMER INTAKE & SLA TRIAGE",
        "tagline": "Provide responsive and predictable service throughout the process from intake through resolution.",
        "description": "Facilitate efficient customer service request process, maintain SLA contractual obligations, and direct tickets intelligently to avoid operational delays.",
        "image_path": "images/module-service.webp",
        "overlay_label": "Live Telemetry & Vibration Analysis Active",
        "capabilities_heading": "Architected for Enterprise-Scale Operations",
        "supporting_label_1": "Audit-Ready Traceability",
        "supporting_label_2": "Bi-Directional Real-Time Sync",
        "metrics": [
            ["14 min", "Average Initial Response Time", "Automated triage and routing for all ticket intake channels"],
            ["98.7%", "Compliance with Contractual SLAs", "Dynamic timer tracking with auto-pausing during customer holds"],
            ["92%", "First-Touch Resolution Rate", "Arming intake coordinators with diagnostic trees and asset history"],
        ],
        "features": [
            {"title": "Multi-Channel Intake", "desc": "Capture service request intake via requester portal, email parser, emergency dispatch line, and connected IoT trigger alerts.", "icon": "file-text"},
            {"title": "Dynamic SLA Timers", "desc": "Automatically generated response and resolution timers based on priority, operating calendars, and contractual obligations.", "icon": "clock"},
            {"title": "Client Portal Access", "desc": "Self-service access for internal business units and customers to report problems, monitor progress, and authorize work.", "icon": "globe"},
            {"title": "First-Time Fix Analysis", "desc": "Pinpoint common root causes, gauge resolution velocity, and improve triage strategies using historical data.", "icon": "bar-chart"},
        ],
        "deep_dive": {
            "title": "Predictable Service Intake to Resolution",
            "p1": "The field service operation breaks down at the point of intake where lack of problem definition and manual ticket routing result in delayed response. FieldOps Nexus enables predictable service intake with guided symptom entry, automatic problem prioritization, and instant SLA clock start time.",
            "p2": "After approval, tickets easily transform into scheduled work orders complete with parts needs, matching technician skills, and customer communications.",
        }
    },

    "work-order-management": {
        "title": "Work Order Management",
        "subtitle": "END-TO-END TASK ORCHESTRATION",
        "tagline": "Plan, assign, and track work orders with absolute clarity.",
        "description": "Equip planners and technicians with clear digital work orders, parts staging, safety checklists, and audit-ready digital signatures.",
        "image_path": "images/module-work-orders.webp",
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
        "image_path": "images/module-inventory.webp",
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
        "tagline": "Get ahead of breakdowns with proactive maintenance.",
        "description": "Automate maintenance planning, identify equipment degradation trends, and switch from reactive to proactive reliability.",
        "image_path": "images/module-maintenance.webp",
        "overlay_label": "Scheduled Preventive Maintenance Automated",
        "capabilities_heading": "Built for Enterprise-Scale Operations",
        "supporting_label_1": "Audit-Ready Traces",
        "supporting_label_2": "Live Bi-Directional Data Sync",
        "runtime_title": "Maintenance Management Live Run-Time Configuration",
        "metrics": [
            ["96.4%", "PM Plan Compliance", "Completion of scheduled work inside the scope of approved maintenance grace windows"],
            ["42%", "Reducing Emergency Work Orders", "Result of systematic time and meter-based maintenance"],
            ["1,200+", "PM Plans Executed", "Enterprise standardization of maintenance procedures for all rotating equipment"],
        ],
        "features": [
            {"title": "Time and Meter-Based PMs", "desc": "Schedule PMs based on days passed, machine hours, production batches, and blackout periods.", "icon": "calendar"},
            {"title": "Inspection Checklists", "desc": "Guided inspection process with quantitative measurement thresholds and mandatory photographic evidence.", "icon": "clipboard-check"},
            {"title": "Condition-Based Monitoring", "desc": "Integrate data about vibration, thermal, and oil analysis in order to spot mechanical degradation prior to functional failure.", "icon": "activity"},
            {"title": "Compliance Audits", "desc": "Download tamper-proof history of maintenance activities for OSHA, ISO 55001, EPA, and corporate compliance audits.", "icon": "shield"},
        ],
        "deep_dive": {
            "title": "From Reactive Repairs to Asset Reliability",
            "p1": "The most prominent source of avoidable operational costs in contemporary industrial operations are unscheduled breakdowns. FieldOps Nexus automates the traditional calendar alerts with dynamic recurrence maintenance engines.",
            "p2": "Condition monitoring algorithms assess telemetry data like vibration velocity, bearing temperature, and pressure differences, creating proactive work orders before mechanical failures lead to shutdowns.",
        },
        "runtime_configs": [
            {
                "title": "Data Security & Tenant Isolation",
                "desc": "Row-level security with tenant-specific cryptographic keys",
                "status": "Enforced",
            },
            {
                "title": "Mobile Field Offline-First Availability",
                "desc": "Local offline cache with automatic delta sync on reconnect",
                "status": "Active",
            },
            {
                "title": "Regulatory Compliance Log",
                "desc": "Append-only changelog tracking every actor, timestamp & IP",
                "status": "Verified",
            },
        ],
    },

    "workforce-management": {
        "title": "Workforce Management",
        "subtitle": "TECHNICIAN DISPATCH & SKILL MATRICES",
        "tagline": "Give every field team member the context to do their best work.",
        "description": "Coordinate technician schedules, track real-time job progression, and empower field teams with intuitive mobile tools.",
        "image_path": "images/module-workforce.webp",
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
            "p1": "Every plant, facility, and utility depends on skilled people working in coordination. FieldOps Nexus helps teams manage workforce operations with clear task assignments, reliable access to information, and less administrative overhead—so technicians and engineers can focus on safe, efficient work.",
            "p2": "Validate skills and qualifications before assigning work, improve workforce readiness, and maintain consistent compliance across demanding operational environments.",
        }
    },

    "analytics-reporting": {
        "title": "Analytics & Reporting",
        "subtitle": "EXECUTIVE OPERATIONAL INTELLIGENCE",
        "tagline": "Make your decisions confidently from your operational data.",
        "description": "Gaining full visibility on executive level into MTTR, technician productivity, cost of parts, and SLA performance for all enterprise locations.",
        "image_path": "images/module-analytics.webp",
        "overlay_label": "Real-Time KPI Streaming Pipeline",
        "capabilities_heading": "Designed for Enterprise Class Operations",
        "metrics": [
            ["50+", "Standard KPI Metrics", "Equipment Reliability, Labor Efficiency, Inventory Turn Rate, SLA Health"],
            ["Real-Time", "Dashboard Refresh", "Data streaming technology that eliminates end of month reporting cycle."],
            ["$420K", "Saved Annually", "Through identification of rogue parts usage and recurrent failure causes."],
        ],
        "features": [
            {"title": "MTTR & MTBF Trends", "desc": "Tracking of MTTR and MTBF trends by equipment classes to measure reliability investments.", "icon": "trending-up"},
            {"title": "Cost & Budget Analytics", "desc": "Consolidation of internal labor hours, external invoice amounts, and costs of parts replacements against operating budget.", "icon": "bar-chart"},
            {"title": "SLA Compliance Reporting", "desc": "Details on response time compliance rate, breach penalty, and department performance rating.", "icon": "clock"},
            {"title": "Custom Business Intelligence Reports Export", "desc": "Scheduled exports to Power BI, Snowflake, Tableau, and enterprise data lakes in parquet and csv file formats.", "icon": "database"},
        ],
        "deep_dive": {
            "title": "Operational Intelligence for Decision Making",
            "p1": "Industrial enterprises generate millions of operational data points in work orders, telemetry data, and inventory transactions. FieldOps Nexus makes sense out of these operational exhaust.",
            "p2": "Interactive dashboards allow directors to drill down from high-level corporate uptime metrics to individual machine failure modes, identifying capital replacement priorities with quantifiable ROI.",
        }
    },

    "audit-traceability": {
        "title": "Audit & Traceability",
        "subtitle": "OPERATIONAL ACTIVITY & VERIFICATION HISTORY",
        "tagline": "Maintain a complete history of all operational activities.",
        "description": "Maintain clear operational history for internal reviews with digital activity records, photographic attachments, and timestamped supervisor sign-offs.",
        "image_path": "images/audit-traceability.webp",
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
        "image_path": "images/left.webp",
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
        "image_path": "images/center.webp",
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
        "image_path": "images/right.webp",
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
        "image_path": "images/fieldops-workflow-visual.webp",
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
        "title": "Connected Data",
        "subtitle": "UNIFIED SERVICE & OPERATIONAL INFORMATION",
        "tagline": "Connect operational information between teams, locations, assets, service requests, and work orders to provide a consistent view of service operations.",
        "description": "Get rid of operational blind spots by tying every asset telemetry data point, every customer service request, every work order checklist, and every inventory part into a relational data model.",
        "image_path": "images/operational-visibility.webp",
        "overlay_label": "Relational Operational Graph Synced",
        "capabilities_heading": "Enterprise Scalable",
        "supporting_label_1": "Audit-Ready Traceability",
        "supporting_label_2": "Real-Time Bi-Directional Synchronization",
        "metrics": [
            ["0 Silos", "Unified Operational Schema", "Fully connected: Assets, requests, work orders, and spare parts."],
            ["Connected", "Lifecycle Traceability", "From initial diagnosis and telemetry data to verified customer signature."],
            ["Direct", "Information Retrieval", "Historical equipment data available in milliseconds."],
        ],
        "features": [
            {"title": "Relational Operational Graph", "desc": "Each work order and part is directly linked to the parent asset genealogy and history.", "icon": "database"},
            {"title": "Zero Double-Entry", "desc": "Technician diagnostic comments are effortlessly transferred from intake ticket to work order and receipt invoice.", "icon": "refresh-cw"},
            {"title": "Mobile Pedigree Access", "desc": "Scan physical machine QR codes to access manual, schematics, and prior work orders immediately offline.", "icon": "search"},
            {"title": "Operational Audit Trail", "desc": "Structured log entries with microsecond accuracy and cryptographically verifiable actor identification.", "icon": "lock"},
        ],
        "deep_dive": {
            "title": "An End to Operational Data Fragmentation",
            "p1": "FieldOps Nexus brings maintenance records, work orders, sensor data, inventory, and customer communications together in one platform. This gives teams a unified view of operations and reduces the need to switch between separate systems.",
            "p2": "Technicians can view an asset's service history, repairs, calibration records, and live telemetry from one place. This helps teams identify issues quickly, make informed decisions, and resolve problems efficiently.",
        }
    },

    "sla-management": {
        "title": "SLA Management",
        "subtitle": "SERVICE-LEVEL OBLIGATIONS & COMPLIANCE",
        "tagline": "Meet service commitments with faster response times and clear operational accountability.",
        "description": "Monitor your service-level commitments, measure response and resolution times and keep visibility into your operational service level obligations.",
        "image_path": "images/workflow-approval.webp",
        "overlay_label": "Active SLA Countdown Timers Monitored",
        "capabilities_heading": "Built for the Enterprise",
        "supporting_label_1": "Audit Ready Traceability",
        "supporting_label_2": "Real Time Two Way Sync",
        "runtime_title": "SLA Management Configuration",
        "metrics": [
            ["99.4%", "Target SLA Compliance Rate", "Real-time countdown clocks for at-risk tickets that may go out of time"],
            ["4 Tiers", "Escalation Priorities", "P1 Critical (15 min) to P4 Routine (48 hrs) prioritized response policies"],
            ["100%", "Clock Pause Tracking for", "Verifiable clock pauses for customer pending states and part shipments"],
        ],
        "features": [
            {"title": "Tiered SLA Policies", "desc": "Create your own response and resolution windows based on the customer contract, equipment tier, and geographic region.", "icon": "speedometer2"},
            {"title": "Automated Clock Pauses", "desc": "Automatic clock pauses when waiting for access to the tenant site, permits from third parties or shipment of parts with an audit trail.", "icon": "pause"},
            {"title": "Predictive Breach Alerts", "desc": "Visual flags and mobile push alerts when tickets hit 75% and 90% of their allotted time frames for resolution.", "icon": "alert-triangle"},
            {"title": "Service Reports", "desc": "Monthly reports for clients of SLA scorecard showing response times, fix rates and contractual penalty credits.", "icon": "file-text"},
        ],
        "deep_dive": {
            "title": "Guaranteed SLA Compliance Control",
            "p1": "FieldOps Nexus helps organizations maintain service-level commitments through automated SLA tracking, real-time response and resolution monitoring, and clear operational visibility. Integrated countdown timers provide timely alerts, helping teams prioritize requests and respond within agreed service targets.",
            "p2": "Configurable pause controls ensure accurate SLA calculations when work is delayed by client dependencies or supply-chain constraints. Detailed audit records capture timestamps, pause reasons, and status changes, strengthening accountability and supporting compliance across teams.",
        },
        "runtime_configs": [
            {
                "title": "Security",
                "desc": "Row Level Security with Cryptographic Tenants Keys Isolated",
                "status": "Required",
            },
            {
                "title": "Mobile Field Readiness",
                "desc": "Offline-first local cache with delta sync",
                "status": "Active",
            },
            {
                "title": "Regulatory Audit Ledger",
                "desc": "Append-only changelog tracking every actor, timestamp & IP",
                "status": "Verified",
            },
        ],
    },

    "multi-site-management": {
        "title": "Multi-Site Management",
        "subtitle": "DISTRIBUTED OPERATIONS & FACILITY GOVERNANCE",
        "tagline": "Create a single connected operational view of your sites, teams, assets, and services.",
        "description": "Unify your multi-facility portfolio according to global standards and resource pools with visibility into asset condition and maintenance compliance.",
        "image_path": "images/module-organization.webp",
        "overlay_label": "Cross-Site Resource Coordination Active",
        "capabilities_heading": "Designed for Enterprise Scale",
        "single_supporting_label": True,
        "supporting_label_1": "Audit-Ready Traceability",
        "metrics": [
            ["60+", "Operating Facilities Managed", "Industrial plants, commercial distribution centers, and service campuses"],
            ["Cross-Site", "Parts Pooling & Visibility", "Check nearby warehouses before making expensive emergency part deliveries"],
            ["Single Pane", "Fleet Operations Visibility", "Facility uptime, work order and audit status roll-up"],
        ],
        "features": [
            {"title": "Location Master Registry", "desc": "Create standardized directories of locations around the world with defined geofences, contact information, and hours of operation.", "icon": "map-pin"},
            {"title": "Building & Bay Mapping", "desc": "Zoom from region-wide map to plant buildings, production bays, and rooms on the floors.", "icon": "building"},
            {"title": "Fleet Radar Console", "desc": "Interactive real-time dashboard tracking active jobs, alarms, and resource availability at all locations.", "icon": "activity"},
            {"title": "Cross-Site Workforce", "desc": "Assign temporary specialist techs across regional plant groups for handling surges and turnarounds.", "icon": "people"},
        ],
        "deep_dive": {
            "title": "Corporate Governance with Local Flexibility",
            "p1": "Running facilities that span multiple locations demands a delicate balance of corporate standardization and field operational flexibility. FieldOps Nexus gives plant managers the ability to control their own schedules while providing executive management with unified metrics for the portfolio.",
            "p2": "Shared spare parts catalogs enable facilities within a geographical cluster to use their safety stock in emergencies, avoiding expensive emergency freight costs and downtime.",
        }
    },

    "connected-data": {
        "title": "Connected Data",
        "subtitle": "UNIFIED SERVICE & OPERATIONAL INFORMATION",
        "tagline": "Connect operational information between teams, locations, assets, service requests, and work orders to provide a consistent view of service operations.",
        "description": "Get rid of operational blind spots by tying every asset telemetry data point, every customer service request, every work order checklist, and every inventory part into a relational data model.",
        "image_path": "images/connected-data.webp",
        "overlay_label": "Relational Operational Graph Synced",
        "capabilities_heading": "Enterprise Scalable",
        "supporting_label_1": "Audit-Ready Traceability",
        "supporting_label_2": "Real-Time Bi-Directional Synchronization",
        "metrics": [
            ["0 Silos", "Unified Operational Schema", "Fully connected: Assets, requests, work orders, and spare parts."],
            ["Connected", "Lifecycle Traceability", "From initial diagnosis and telemetry data to verified customer signature"],
            ["Direct", "Information Retrieval", "Historical equipment data available in milliseconds"],
        ],
        "features": [
            {"title": "Relational Operational Graph", "desc": "Each work order and part is directly linked to the parent asset genealogy and history.", "icon": "database"},
            {"title": "Zero Double-Entry", "desc": "Technician diagnostic comments are effortlessly transferred from intake ticket to work order and receipt invoice.", "icon": "refresh-cw"},
            {"title": "Mobile Pedigree Access", "desc": "Scan physical machine QR codes to access manual, schematics, and prior work orders immediately offline.", "icon": "search"},
            {"title": "Operational Audit Trail", "desc": "Structured log entries with microsecond accuracy and cryptographically verifiable actor identification.", "icon": "lock"},
        ],
        "deep_dive": {
            "title": "An End to Operational Data Fragmentation",
            "p1": "FieldOps Nexus brings maintenance records, work orders, sensor data, inventory, and customer communications together in one platform. This gives teams a unified view of operations and reduces the need to switch between separate systems.",
            "p2": "Technicians can view an asset's service history, repairs, calibration records, and live telemetry from one place. This helps teams identify issues quickly, make informed decisions, and resolve problems efficiently.",
        }
    },

    "inspection-checklist": {
        "title": "Inspection & Checklist",
        "subtitle": "QUALITY ASSURANCE & SAFETY COMPLIANCE",
        "tagline": "Standardize field inspections and ensure regulatory compliance with digital SOPs.",
        "description": "Deploy dynamic inspection templates, enforce mandatory safety verification gates, and log corrective findings with photo documentation and digital sign-offs.",
        "image_path": "images/workflow-field-operations.webp",
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
        "image_path": "images/workflow-approval.webp",
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
        "image_path": "images/module-assets.webp",
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
        "image_path": "images/smarter-workflows.webp",
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
        "image_path": "images/workflow-field-operations.webp",
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
        "image_path": "images/workflow-asset-management.webp",
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
    "platform-overview",
    "core-capabilities",
    "enterprise-architecture",
    "integrations",
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


