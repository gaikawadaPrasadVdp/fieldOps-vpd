"""M10 Warranty & Contract exports (CSV / XLSX / PDF).

Supports both:
1. Bulk export of all matching/authorized warranty records (CSV, XLSX, PDF).
2. Individual warranty comprehensive document (PDF) for a single warranty record.

Ensures formula injection protection, UTF-8 encoding with BOM for CSV,
proper date formatting, and avoids N+1 queries.
"""
from __future__ import annotations

import csv
import datetime
import html
import io
import re
from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.files.models import Attachment

from . import services
from .models import CoverageAgreement

FORMATS = {
    "csv": ("text/csv; charset=utf-8", "csv"),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "pdf": ("application/pdf", "pdf"),
}

COLUMNS = [
    "Warranty Reference",
    "Title",
    "Type",
    "Status",
    "Provider Name",
    "Provider Contact",
    "Provider Email",
    "Provider Phone",
    "Site Code",
    "Site Name",
    "Start Date",
    "Expiry Date",
    "Duration (Days)",
    "Covered Asset Tags",
    "Covered Asset Names",
    "Asset Serial Numbers",
    "Asset Manufacturers",
    "Asset Models",
    "Covered Work Types",
    "Excluded Work Types",
    "Exclusion Notes",
    "Coverage Terms",
    "SLA Response Terms",
    "SLA Profile",
    "Renewal Alert (Days)",
    "Associated Predecessor Contract",
    "Associated Successor Contract",
    "Total Coverage Checks",
    "Eligible Checks Count",
    "Recent Check Details",
    "Defect / Check Reasons",
    "Active",
    "Deactivation Reason",
    "Created By",
    "Created At",
    "Updated At",
    "Attachments",
]


@dataclass
class Export:
    body: bytes
    content_type: str
    filename: str
    rows: int
    truncated: bool = False


def _safe(value) -> str:
    """Neutralize spreadsheet formula injection for values beginning with =, +, -, @, tab or CR."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _esc(val) -> str:
    """HTML escape for ReportLab Paragraph text."""
    if val is None or val == "":
        return "—"
    return html.escape(str(val))


def _get_attachments_for(agreement) -> list[str]:
    try:
        ct = ContentType.objects.get_for_model(CoverageAgreement)
        attachments = Attachment.objects.for_organization(agreement.organization).filter(
            content_type=ct, object_id=str(agreement.pk)
        )
        return [a.original_name for a in attachments]
    except Exception:
        return []


def rows_for(qs, org) -> list[list[str]]:
    """Build column values for all given agreements with query optimization."""
    today = datetime.date.today()
    items = list(
        qs.select_related("provider", "site", "sla_profile", "renewed_from", "created_by")
        .prefetch_related("covered_assets__asset", "exclusions", "checks__work_order", "checks__checked_by")
    )
    rows = []
    for ag in items:
        # Covered assets
        covered_links = list(ag.covered_assets.all())
        asset_tags = "; ".join(l.asset.asset_tag for l in covered_links if l.asset)
        asset_names = "; ".join(l.asset.name for l in covered_links if l.asset)
        serials = "; ".join(l.asset.serial_number for l in covered_links if l.asset and l.asset.serial_number)
        makers = "; ".join(sorted({l.asset.manufacturer for l in covered_links if l.asset and l.asset.manufacturer}))
        models = "; ".join(sorted({l.asset.model for l in covered_links if l.asset and l.asset.model}))

        # Exclusions & Covered types
        exclusions = list(ag.exclusions.all())
        excluded_types = [e.work_type for e in exclusions]
        covered_types = [w for w in services.WORK_TYPES if w not in excluded_types]

        # Duration
        duration_days = (ag.end_date - ag.start_date).days if (ag.end_date and ag.start_date) else 0

        # Successor renewal
        renewal = None
        try:
            renewal = ag.renewal
        except Exception:
            renewal = None

        # Checks & Claims
        checks = list(ag.checks.all())
        total_checks = len(checks)
        eligible_checks = sum(1 for c in checks if c.eligible)
        check_details_list = []
        defect_reasons = []
        for c in checks[:5]:  # include up to 5 recent checks
            wo_ref = c.work_order.number or c.work_order.order_number if c.work_order else "N/A"
            status_text = "Eligible" if c.eligible else "Ineligible"
            check_details_list.append(f"WO #{wo_ref} ({c.work_type}, {c.reference_date}): {status_text}")
            if c.reason:
                defect_reasons.append(f"WO #{wo_ref}: {c.reason}")

        # Attachments
        att_names = _get_attachments_for(ag)

        row = [
            ag.reference,
            ag.title,
            ag.get_kind_display(),
            ag.state(today),
            ag.provider.name if ag.provider else "",
            ag.provider.contact_name if ag.provider else "",
            ag.provider.email if ag.provider else "",
            ag.provider.phone if ag.provider else "",
            ag.site.code if ag.site else "",
            ag.site.name if ag.site else "",
            ag.start_date.strftime("%Y-%m-%d") if ag.start_date else "",
            ag.end_date.strftime("%Y-%m-%d") if ag.end_date else "",
            str(duration_days),
            asset_tags,
            asset_names,
            serials,
            makers,
            models,
            ", ".join(covered_types),
            ", ".join(excluded_types),
            ag.exclusion_notes or "",
            ag.terms or "",
            ag.sla_terms or "",
            ag.sla_profile.name if ag.sla_profile else "",
            str(ag.renewal_alert_days),
            ag.renewed_from.reference if ag.renewed_from else "",
            renewal.reference if renewal else "",
            str(total_checks),
            str(eligible_checks),
            "; ".join(check_details_list),
            "; ".join(defect_reasons),
            "Yes" if ag.is_active else "No",
            ag.deactivation_reason or "",
            getattr(ag.created_by, "email", "") if ag.created_by else "",
            ag.created_at.strftime("%Y-%m-%d %H:%M:%S") if ag.created_at else "",
            ag.updated_at.strftime("%Y-%m-%d %H:%M:%S") if ag.updated_at else "",
            "; ".join(att_names),
        ]
        rows.append(row)
    return rows


def build_bulk_export(fmt: str, qs, org, *, actor=None, filters_text: str = "") -> Export:
    """Generate bulk export of warranties matching given filters across all pages."""
    if fmt not in FORMATS:
        raise ValueError(f"Unknown export format: {fmt}. Supported formats: csv, xlsx, pdf.")

    rows = rows_for(qs, org)
    stamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    ctype, ext = FORMATS[fmt]
    name = f"warranties_export_{org.slug}_{stamp}.{ext}"

    meta = [
        f"Organization: {org.name}",
        f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} UTC by {getattr(actor, 'email', 'System')}",
        f"Total Records: {len(rows)}",
        f"Active Filters: {filters_text or 'None (All Accessible Records)'}",
    ]

    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([_safe(c) for c in r])
        # Include UTF-8 BOM so Excel opens CSV with proper encoding
        body = ("\ufeff" + buf.getvalue()).encode("utf-8")
    elif fmt == "xlsx":
        body = _build_bulk_xlsx(rows, meta)
    else:
        body = _build_bulk_pdf(rows, meta, org)

    return Export(body, ctype, name, len(rows), False)


def _build_bulk_xlsx(rows, meta) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Warranty Details"

    # Header styling
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    ws.append(COLUMNS)
    for col_idx, cell in enumerate(ws[1], start=1):
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    ws.row_dimensions[1].height = 28

    # Data rows
    row_font = Font(name="Calibri", size=10)
    for r in rows:
        ws.append([_safe(c) for c in r])

    for row_cells in ws.iter_rows(min_row=2, max_row=len(rows) + 1):
        for cell in row_cells:
            cell.font = row_font
            cell.border = thin_border

    ws.freeze_panes = "A2"

    # Auto-adjust column widths (with sane caps)
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col[:50]:  # sample first 50 rows
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(12, min(max_len + 3, 40))

    # Metadata sheet
    ws_meta = wb.create_sheet("Export Information")
    ws_meta.append(["FieldOps Nexus — Warranty Export Summary"])
    ws_meta["A1"].font = Font(name="Calibri", size=14, bold=True, color="1E293B")
    ws_meta.append([])
    for line in meta:
        ws_meta.append([line])
        ws_meta.cell(row=ws_meta.max_row, column=1).font = Font(name="Calibri", size=10)
    ws_meta.column_dimensions["A"].width = 50

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_bulk_pdf(rows, meta, org) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=32,
        title=f"Warranties Export — {org.name}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BulkTitle",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        "BulkMeta",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )
    cell_style = ParagraphStyle(
        "BulkCell",
        parent=styles["Normal"],
        fontSize=7,
        leading=8.5,
        textColor=colors.HexColor("#1e293b"),
    )
    cell_bold = ParagraphStyle(
        "BulkCellBold",
        parent=styles["Normal"],
        fontSize=7,
        leading=8.5,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0f172a"),
    )
    header_style = ParagraphStyle(
        "BulkHeader",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=9,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    story = [
        Paragraph("FieldOps Nexus · Warranties & Contracts Report", title_style),
        Paragraph(" | ".join(_esc(m) for m in meta), meta_style),
        Spacer(1, 10),
    ]

    # Subset of core columns for landscape summary table
    headers = ["Reference", "Title", "Type", "Status", "Provider", "Site", "Valid Dates", "Covered Assets"]
    table_data = [[Paragraph(h, header_style) for h in headers]]

    for r in rows:
        ref = r[0]
        title = r[1]
        kind = r[2]
        status = r[3]
        provider = r[4]
        site = r[8]
        valid = f"{r[10]} → {r[11]}"
        assets = r[13] if r[13] else "No assets"

        table_data.append([
            Paragraph(_esc(ref), cell_bold),
            Paragraph(_esc(title), cell_style),
            Paragraph(_esc(kind), cell_style),
            Paragraph(_esc(status), cell_bold),
            Paragraph(_esc(provider), cell_style),
            Paragraph(_esc(site), cell_style),
            Paragraph(_esc(valid), cell_style),
            Paragraph(_esc(assets), cell_style),
        ])

    table = Table(table_data, repeatRows=1, colWidths=[80, 130, 80, 60, 110, 45, 120, 165])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    doc.build(story)
    return buf.getvalue()


def _get_canvasmaker():
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas

    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_page_decorations(num_pages)
                super().showPage()
            super().save()

        def _draw_page_decorations(self, page_count):
            self.saveState()
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawString(36, 20, "FieldOps Nexus — Confidential Individual Warranty Details Report")
            page_str = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(self._pagesize[0] - 36, 20, page_str)
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(36, 30, self._pagesize[0] - 36, 30)
            self.restoreState()

    return NumberedCanvas


def build_single_warranty_pdf(agreement, org, *, actor=None) -> bytes:
    """Generate an individual, properly formatted PDF document for one selected warranty."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=42,
        title=f"Warranty Report — {agreement.reference}",
        author="FieldOps Nexus",
    )

    styles = getSampleStyleSheet()

    # Typography styles
    brand_style = ParagraphStyle(
        "BrandHeader",
        parent=styles["Normal"],
        fontSize=10,
        leading=12,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#2563eb"),
    )
    report_title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2,
    )
    meta_sub_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#64748b"),
    )
    section_h_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=11,
        leading=14,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=12,
        spaceAfter=4,
    )
    lbl_style = ParagraphStyle(
        "KVLabel",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#475569"),
    )
    val_style = ParagraphStyle(
        "KVValue",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )
    table_hdr_style = ParagraphStyle(
        "TableHdr",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1e293b"),
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=9.5,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0f172a"),
    )
    callout_ref_style = ParagraphStyle(
        "CalloutRef",
        parent=styles["Normal"],
        fontSize=14,
        leading=16,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1e293b"),
    )
    callout_sub_style = ParagraphStyle(
        "CalloutSub",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )
    status_badge_style = ParagraphStyle(
        "StatusBadge",
        parent=styles["Normal"],
        fontSize=10,
        leading=12,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=1,  # Center
    )

    story = []

    # 1. Branding Header
    brand_row = [
        [
            Paragraph("<b>FIELDOPS NEXUS</b> · Commercial Asset &amp; Contract ERP", brand_style),
            Paragraph(f"Organization: <b>{_esc(org.name)}</b>", ParagraphStyle("OrgR", parent=meta_sub_style, alignment=2)),
        ]
    ]
    brand_table = Table(brand_row, colWidths=[320, 203])
    brand_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(brand_table)
    story.append(Spacer(1, 4))

    # 2. Main Title Banner & Prominent Reference Callout
    today = datetime.date.today()
    state_str = agreement.state(today)
    state_color = {
        "ACTIVE": colors.HexColor("#16a34a"),
        "UPCOMING": colors.HexColor("#2563eb"),
        "EXPIRED": colors.HexColor("#dc2626"),
        "INACTIVE": colors.HexColor("#64748b"),
    }.get(state_str, colors.HexColor("#64748b"))

    story.append(Paragraph("Warranty Details Report", report_title_style))
    gen_time_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    actor_str = getattr(actor, "email", "Authorized User") if actor else "Authorized User"
    story.append(Paragraph(f"Generated on {gen_time_str} UTC by {actor_str} | Confidential Asset Intelligence", meta_sub_style))
    story.append(Spacer(1, 8))

    # Prominent Reference Box
    callout_data = [
        [
            [
                Paragraph(f"Warranty ID: {_esc(agreement.reference)}", callout_ref_style),
                Paragraph(f"{_esc(agreement.title)} ({_esc(agreement.get_kind_display())})", callout_sub_style),
            ],
            Paragraph(state_str, status_badge_style),
        ]
    ]
    callout_table = Table(callout_data, colWidths=[415, 108])
    callout_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#f8fafc")),
        ("BACKGROUND", (1, 0), (1, 0), state_color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (0, 0), 10),
        ("RIGHTPADDING", (1, 0), (1, 0), 10),
    ]))
    story.append(callout_table)
    story.append(Spacer(1, 10))

    # 3. Section: Warranty Information
    story.append(Paragraph("1. Warranty &amp; Contract Information", section_h_style))
    duration_days = (agreement.end_date - agreement.start_date).days if (agreement.end_date and agreement.start_date) else 0
    days_left = (agreement.end_date - today).days if agreement.end_date else 0
    valid_window = f"{agreement.start_date.strftime('%d %b %Y')} → {agreement.end_date.strftime('%d %b %Y')}"
    duration_text = f"{duration_days} days ({days_left} days remaining)" if days_left >= 0 else f"{duration_days} days (Expired {abs(days_left)} days ago)"

    prov = agreement.provider
    prov_text = prov.name if prov else "None"
    prov_contact = f"{prov.contact_name} ({prov.email or 'No email'}, {prov.phone or 'No phone'})" if prov and (prov.contact_name or prov.email) else (prov.name if prov else "—")
    site_text = f"{agreement.site.code} — {agreement.site.name}" if agreement.site else "—"
    sla_prof_text = agreement.sla_profile.name if agreement.sla_profile else "Site / Org Default SLA"

    info_data = [
        [
            Paragraph("Warranty ID", lbl_style), Paragraph(_esc(agreement.reference), val_style),
            Paragraph("Warranty Title", lbl_style), Paragraph(_esc(agreement.title), val_style),
        ],
        [
            Paragraph("Contract Type", lbl_style), Paragraph(_esc(agreement.get_kind_display()), val_style),
            Paragraph("Status", lbl_style), Paragraph(_esc(state_str), val_style),
        ],
        [
            Paragraph("Valid Period", lbl_style), Paragraph(_esc(valid_window), val_style),
            Paragraph("Duration", lbl_style), Paragraph(_esc(duration_text), val_style),
        ],
        [
            Paragraph("Provider", lbl_style), Paragraph(_esc(prov_text), val_style),
            Paragraph("Provider Contact", lbl_style), Paragraph(_esc(prov_contact), val_style),
        ],
        [
            Paragraph("Site / Facility", lbl_style), Paragraph(_esc(site_text), val_style),
            Paragraph("Internal SLA Profile", lbl_style), Paragraph(_esc(sla_prof_text), val_style),
        ],
        [
            Paragraph("Response SLA Terms", lbl_style), Paragraph(_esc(agreement.sla_terms or "None specified"), val_style),
            Paragraph("Active Governance", lbl_style), Paragraph("Active" if agreement.is_active else f"Deactivated ({agreement.deactivation_reason})", val_style),
        ],
    ]
    info_table = Table(info_data, colWidths=[110, 151, 110, 152])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 10))

    # 4. Section: Covered Assets
    story.append(Paragraph(f"2. Covered Assets ({agreement.covered_assets.count()})", section_h_style))
    covered_links = list(agreement.covered_assets.select_related("asset__site", "asset__zone").all())
    if covered_links:
        asset_headers = ["Asset ID / Tag", "Asset Name", "Manufacturer", "Model", "Serial Number", "Status"]
        asset_table_data = [[Paragraph(h, table_hdr_style) for h in asset_headers]]
        for l in covered_links:
            a = l.asset
            if not a:
                continue
            status_display = a.get_status_display() if hasattr(a, "get_status_display") else a.status
            asset_table_data.append([
                Paragraph(_esc(a.asset_tag), table_cell_bold),
                Paragraph(_esc(a.name), table_cell_style),
                Paragraph(_esc(a.manufacturer or "—"), table_cell_style),
                Paragraph(_esc(a.model or "—"), table_cell_style),
                Paragraph(_esc(a.serial_number or "—"), table_cell_style),
                Paragraph(_esc(status_display), table_cell_style),
            ])
        asset_table = Table(asset_table_data, repeatRows=1, colWidths=[90, 130, 80, 73, 85, 65])
        asset_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(asset_table)
    else:
        story.append(Paragraph("<i>No assets are currently assigned to this coverage agreement.</i>", val_style))
    story.append(Spacer(1, 10))

    # 5. Section: Coverage Details, Covered Services & Exclusions
    story.append(Paragraph("3. Coverage Details, Terms &amp; Exclusions", section_h_style))
    exclusions = list(agreement.exclusions.all())
    excluded_types = [e.get_work_type_display() if hasattr(e, "get_work_type_display") else e.work_type for e in exclusions]
    covered_types = [w for w in services.WORK_TYPES if w not in [e.work_type for e in exclusions]]

    cov_data = [
        [
            Paragraph("Coverage Terms &amp; Conditions", lbl_style),
            Paragraph(_esc(agreement.terms or "Standard manufacturer/vendor agreement terms apply."), val_style),
        ],
        [
            Paragraph("Covered Work Types / Services", lbl_style),
            Paragraph(", ".join(covered_types) if covered_types else "None", val_style),
        ],
        [
            Paragraph("Excluded Work Types", lbl_style),
            Paragraph(", ".join(excluded_types) if excluded_types else "None (All standard services eligible)", val_style),
        ],
        [
            Paragraph("Specific Exclusion Notes", lbl_style),
            Paragraph(_esc(agreement.exclusion_notes or "None"), val_style),
        ],
    ]
    cov_table = Table(cov_data, colWidths=[150, 373])
    cov_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(cov_table)
    story.append(Spacer(1, 10))

    # 6. Section: Claims & Eligibility Decision History
    checks = list(
        agreement.checks.select_related("work_order", "asset", "checked_by")
        .order_by("-created_at")[:20]
    )
    story.append(Paragraph(f"4. Warranty Claim &amp; Eligibility Check History ({agreement.checks.count()})", section_h_style))
    if checks:
        claim_headers = ["Work Order #", "Asset Tag", "Work Type", "Date", "Status", "Reason / Defect Description", "Checked By"]
        claim_table_data = [[Paragraph(h, table_hdr_style) for h in claim_headers]]
        for c in checks:
            wo_num = c.work_order.number or c.work_order.order_number if c.work_order else "N/A"
            tag = c.asset.asset_tag if c.asset else "—"
            res = "Eligible" if c.eligible else "Ineligible"
            checker = getattr(c.checked_by, "email", "System") if c.checked_by else "System"
            claim_table_data.append([
                Paragraph(_esc(wo_num), table_cell_bold),
                Paragraph(_esc(tag), table_cell_style),
                Paragraph(_esc(c.work_type), table_cell_style),
                Paragraph(_esc(c.reference_date.strftime("%Y-%m-%d") if c.reference_date else "—"), table_cell_style),
                Paragraph(_esc(res), table_cell_bold),
                Paragraph(_esc(c.reason or "—"), table_cell_style),
                Paragraph(_esc(checker), table_cell_style),
            ])
        claim_table = Table(claim_table_data, repeatRows=1, colWidths=[70, 65, 55, 58, 55, 140, 80])
        claim_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(claim_table)
    else:
        story.append(Paragraph("<i>No warranty claims or coverage checks have been recorded for this agreement yet.</i>", val_style))
    story.append(Spacer(1, 10))

    # 7. Section: Renewal Information & Governance
    story.append(Paragraph("5. Renewal Information &amp; Predecessor/Successor Links", section_h_style))
    renewal = None
    try:
        renewal = agreement.renewal
    except Exception:
        renewal = None

    renew_data = [
        [
            Paragraph("Renewal Alert Threshold", lbl_style),
            Paragraph(f"{agreement.renewal_alert_days} days before expiration", val_style),
            Paragraph("Renewal Alerted At", lbl_style),
            Paragraph(agreement.renewal_alerted_at.strftime("%Y-%m-%d %H:%M:%S") if agreement.renewal_alerted_at else "Not alerted yet", val_style),
        ],
        [
            Paragraph("Renewed From (Predecessor)", lbl_style),
            Paragraph(_esc(agreement.renewed_from.reference if agreement.renewed_from else "None (Initial Contract)"), val_style),
            Paragraph("Renewed As (Successor)", lbl_style),
            Paragraph(_esc(renewal.reference if renewal else "None (Not Renewed)"), val_style),
        ],
    ]
    renew_table = Table(renew_data, colWidths=[130, 131, 130, 132])
    renew_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(renew_table)
    story.append(Spacer(1, 10))

    # 8. Section: Audit, Lifecycle & Attachments
    att_names = _get_attachments_for(agreement)
    att_str = ", ".join(att_names) if att_names else "No attachments linked"
    meta_data = [
        [
            Paragraph("Created At", lbl_style), Paragraph(agreement.created_at.strftime("%Y-%m-%d %H:%M:%S") if agreement.created_at else "—", val_style),
            Paragraph("Created By", lbl_style), Paragraph(_esc(getattr(agreement.created_by, "email", "System")), val_style),
        ],
        [
            Paragraph("Last Updated", lbl_style), Paragraph(agreement.updated_at.strftime("%Y-%m-%d %H:%M:%S") if agreement.updated_at else "—", val_style),
            Paragraph("Associated Documents", lbl_style), Paragraph(_esc(att_str), val_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[110, 151, 110, 152])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(meta_table)

    canvasmaker = _get_canvasmaker()
    doc.build(story, canvasmaker=canvasmaker)
    return buf.getvalue()


def clean_ref_filename(reference: str, ext: str = "pdf") -> str:
    """Generate safe, unique filename for an individual warranty."""
    clean = re.sub(r"[^A-Za-z0-9_-]", "_", reference).strip("_") or "warranty"
    today_str = timezone.now().strftime("%Y-%m-%d")
    return f"Warranty_{clean}_{today_str}.{ext}"


from django.http import HttpResponse

from . import selectors


def export_agreements_csv(qs, org) -> HttpResponse:
    """Download filtered coverage agreements as CSV."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    response["Content-Disposition"] = f'attachment; filename="warranties_contracts_{org.slug}_{timestamp}.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Reference",
        "Title",
        "Type",
        "Provider",
        "Site Code",
        "Start Date",
        "End Date",
        "State",
        "Active",
        "SLA Terms",
        "SLA Profile",
        "Renewal Alert (Days)",
        "Covered Assets Count",
        "Excluded Work Types",
        "Terms",
        "Created At",
    ])
    today = datetime.date.today()
    for a in qs.select_related("provider", "site", "sla_profile").prefetch_related("covered_assets__asset", "exclusions"):
        assets_count = a.covered_assets.count()
        exclusions = ", ".join(e.get_work_type_display() if hasattr(e, "get_work_type_display") else e.work_type for e in a.exclusions.all())
        writer.writerow([
            a.reference,
            a.title,
            a.get_kind_display(),
            a.provider.name if a.provider else "",
            a.site.code if a.site else "",
            a.start_date.isoformat() if a.start_date else "",
            a.end_date.isoformat() if a.end_date else "",
            a.state(today),
            "Yes" if a.is_active else "No",
            a.sla_terms or "",
            a.sla_profile.name if a.sla_profile else "",
            a.renewal_alert_days,
            assets_count,
            exclusions,
            a.terms or "",
            a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
        ])
    return response


def export_single_agreement_csv(ag) -> HttpResponse:
    """Download a single coverage agreement with its metadata, terms, and covered assets as CSV."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_ref = ag.reference.replace('/', '_').replace('\\', '_')
    response["Content-Disposition"] = f'attachment; filename="warranty_{safe_ref}_{timestamp}.csv"'
    writer = csv.writer(response)
    today = datetime.date.today()
    
    # Header Section
    writer.writerow(["AGREEMENT DETAILS"])
    writer.writerow(["Reference", ag.reference])
    writer.writerow(["Title", ag.title])
    writer.writerow(["Type", ag.get_kind_display()])
    writer.writerow(["State", ag.state(today)])
    writer.writerow(["Active", "Yes" if ag.is_active else "No"])
    writer.writerow(["Provider Name", ag.provider.name if ag.provider else ""])
    writer.writerow(["Provider Email", ag.provider.email if ag.provider else ""])
    writer.writerow(["Provider Phone", ag.provider.phone if ag.provider else ""])
    writer.writerow(["Site Code", ag.site.code if ag.site else ""])
    writer.writerow(["Site Name", ag.site.name if ag.site else ""])
    writer.writerow(["Start Date", ag.start_date.isoformat() if ag.start_date else ""])
    writer.writerow(["End Date", ag.end_date.isoformat() if ag.end_date else ""])
    writer.writerow(["SLA Terms", ag.sla_terms or ""])
    writer.writerow(["SLA Profile", ag.sla_profile.name if ag.sla_profile else ""])
    exclusions = ", ".join(e.get_work_type_display() if hasattr(e, "get_work_type_display") else e.work_type for e in ag.exclusions.all()) or "None"
    writer.writerow(["Exclusions", exclusions])
    writer.writerow(["Terms", ag.terms or ""])
    if ag.exclusion_notes:
        writer.writerow(["Exclusion Notes", ag.exclusion_notes])
    writer.writerow([])
    
    # Covered Assets Section
    writer.writerow(["COVERED ASSETS"])
    writer.writerow(["Asset Tag", "Asset Name", "Category", "Serial Number", "Status"])
    for link in selectors.covered_assets_for(ag).select_related("asset__category"):
        ast = link.asset
        writer.writerow([
            ast.asset_tag,
            ast.name,
            ast.category.name if ast.category else "",
            ast.serial_number or "",
            ast.get_status_display() if hasattr(ast, "get_status_display") else ast.status,
        ])
    return response


def export_expiry_csv(rows, org, days) -> HttpResponse:
    """Download expiring coverage agreements forecast as CSV."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    response["Content-Disposition"] = f'attachment; filename="expiring_warranties_{org.slug}_{days}d_{timestamp}.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Reference",
        "Title",
        "Type",
        "Provider",
        "Site Code",
        "End Date",
        "Days Left",
        "Renewed",
        "Covered Assets Count",
    ])
    today = datetime.date.today()
    for a in rows:
        writer.writerow([
            a.reference,
            a.title,
            a.get_kind_display(),
            a.provider.name if a.provider else "",
            a.site.code if a.site else "",
            a.end_date.isoformat() if a.end_date else "",
            (a.end_date - today).days,
            "Yes" if getattr(a, "renewed", False) else "No",
            a.covered_assets.count(),
        ])
    return response
