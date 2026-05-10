"""
Geração de PDF usando ReportLab (puro Python, sem dependências de C/HTML).
Parser de markdown simples otimizado pro nosso layout específico.
"""
import io
import re
from typing import Optional


def render_to_pdf(markdown_text: str, title: str = "RepoMind Review") -> bytes:
    """
    Gera PDF a partir do markdown do review.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor
        from reportlab.lib.enums import TA_LEFT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak, KeepTogether
        )
        from reportlab.pdfgen import canvas
    except ImportError:
        raise RuntimeError(
            "reportlab not installed. Run: pip install reportlab"
        )

    # ── Colors (AMD theme) ─────────────────────────────────────────────
    ACCENT = HexColor("#e8400c")
    DARK = HexColor("#1a1a1a")
    GRAY = HexColor("#666666")
    LIGHT_GRAY = HexColor("#f4f4f4")
    BORDER = HexColor("#dddddd")
    GREEN = HexColor("#00a878")
    RED = HexColor("#cc3333")
    ORANGE = HexColor("#e8800c")
    YELLOW = HexColor("#b89000")
    CODE_BG = HexColor("#f8f8f8")

    # ── Styles ─────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=22,
        textColor=ACCENT,
        spaceAfter=4,
        spaceBefore=0,
        leading=26,
        fontName="Helvetica-Bold",
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=DARK,
        spaceAfter=8,
        spaceBefore=18,
        leading=18,
        fontName="Helvetica-Bold",
    )
    h3_style = ParagraphStyle(
        "H3",
        parent=styles["Heading3"],
        fontSize=11,
        textColor=DARK,
        spaceAfter=6,
        spaceBefore=12,
        leading=14,
        fontName="Helvetica-Bold",
    )
    h4_style = ParagraphStyle(
        "H4",
        fontSize=10,
        textColor=ACCENT,
        spaceAfter=4,
        spaceBefore=10,
        leading=13,
        fontName="Courier-Bold",
        backColor=HexColor("#fef4ee"),
        borderPadding=4,
    )
    normal = ParagraphStyle(
        "Normal2",
        parent=styles["Normal"],
        fontSize=10,
        textColor=DARK,
        spaceAfter=4,
        leading=14,
        fontName="Helvetica",
    )
    code_style = ParagraphStyle(
        "Code",
        fontSize=9,
        textColor=DARK,
        leading=12,
        fontName="Courier",
        backColor=CODE_BG,
        borderPadding=8,
        borderColor=ACCENT,
        borderWidth=0,
        leftIndent=8,
        spaceAfter=8,
        spaceBefore=4,
    )
    meta_style = ParagraphStyle(
        "Meta",
        fontSize=9,
        textColor=GRAY,
        spaceAfter=2,
        fontName="Helvetica",
    )
    list_style = ParagraphStyle(
        "List",
        fontSize=10,
        textColor=DARK,
        leading=14,
        leftIndent=14,
        bulletIndent=4,
        spaceAfter=2,
        fontName="Helvetica",
    )

    # ── Parse and convert markdown to flowables ────────────────────────
    flowables = []
    lines = markdown_text.split("\n")
    i = 0
    in_table = False
    table_rows = []
    in_code = False
    code_lines = []

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        rows = [r for r in table_rows if not all(re.match(r"^[\s\-:]+$", c or "") for c in r)]
        if not rows:
            table_rows = []
            return
        ncols = max(len(r) for r in rows)
        rows = [r + [""] * (ncols - len(r)) for r in rows]
        cell_style = ParagraphStyle(
            "Cell", fontSize=9, textColor=DARK, leading=12, fontName="Helvetica"
        )
        header_cell_style = ParagraphStyle(
            "CellH", fontSize=9, textColor=DARK, leading=12, fontName="Helvetica-Bold"
        )

        table_data = []
        for ri, row in enumerate(rows):
            new_row = []
            for cell in row:
                style_for_cell = header_cell_style if ri == 0 else cell_style
                new_row.append(Paragraph(_inline_md(cell.strip()), style_for_cell))
            table_data.append(new_row)

        col_widths = [16 * cm / ncols] * ncols
        t = Table(table_data, colWidths=col_widths, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GRAY),
            ("TEXTCOLOR", (0, 0), (-1, 0), DARK),
            ("LINEBELOW", (0, 0), (-1, 0), 1.5, BORDER),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        flowables.append(t)
        flowables.append(Spacer(1, 8))
        table_rows = []

    def flush_code():
        nonlocal code_lines
        if not code_lines:
            return
        code_text = "\n".join(code_lines)
        code_text = code_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        code_text = code_text.replace("\n", "<br/>")
        flowables.append(Paragraph(f'<font face="Courier" size="9">{code_text}</font>', code_style))
        code_lines = []

    while i < len(lines):
        line = lines[i]

        # Code block delimiter
        if line.strip().startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        # Table detection
        if "|" in line and not line.startswith("    "):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells:
                if not in_table:
                    in_table = True
                table_rows.append(cells)
                i += 1
                continue
        elif in_table:
            flush_table()
            in_table = False

        # Horizontal rule
        if line.strip() == "---":
            flowables.append(Spacer(1, 4))
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        # Headings
        if line.startswith("#### "):
            flowables.append(Paragraph(_inline_md(line[5:]), h4_style))
        elif line.startswith("### "):
            flowables.append(Paragraph(_inline_md(line[4:]), h3_style))
        elif line.startswith("## "):
            flowables.append(Paragraph(_inline_md(line[3:]), h2_style))
        elif line.startswith("# "):
            flowables.append(Paragraph(_inline_md(line[2:]), title_style))
            flowables.append(HRFlowable(width="100%", thickness=2, color=ACCENT))
            flowables.append(Spacer(1, 8))

        # List items
        elif line.lstrip().startswith("- "):
            content = line.lstrip()[2:]
            flowables.append(Paragraph("• " + _inline_md(content), list_style))

        # Empty line
        elif not line.strip():
            flowables.append(Spacer(1, 4))

        # Regular paragraph
        else:
            txt = _inline_md(line)
            # Detecta se é meta (começa com **Repository:**, etc no início)
            if line.startswith("**") and ":**" in line[:30]:
                flowables.append(Paragraph(txt, meta_style))
            else:
                flowables.append(Paragraph(txt, normal))

        i += 1

    if in_code:
        flush_code()
    if in_table:
        flush_table()

    # ── Build PDF ──────────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=title,
        author="RepoMind",
    )

    def add_footer(canvas_obj, doc):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(GRAY)
        canvas_obj.drawCentredString(
            A4[0] / 2,
            1 * cm,
            f"RepoMind · {doc.page}"
        )
        canvas_obj.restoreState()

    doc.build(flowables, onFirstPage=add_footer, onLaterPages=add_footer)
    buf.seek(0)
    return buf.read()


# ── Inline markdown helpers ────────────────────────────────────────────

def _inline_md(text: str) -> str:
    """Converte markdown inline (bold, code, italic) para HTML do ReportLab."""
    if not text:
        return ""
    # Escape HTML basics first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold: **text** -> <b>text</b>
    text = re.sub(r"\*\*([^*\n]+?)\*\*", r"<b>\1</b>", text)
    # Inline code: `code` -> styled span
    text = re.sub(
        r"`([^`\n]+?)`",
        r'<font face="Courier" size="9" color="#c7254e" backColor="#f4f4f4">\1</font>',
        text
    )
    # Italic: *text* -> <i>text</i> (depois de **bold** pra não conflitar)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text)
    # Links: [text](url) -> link
    text = re.sub(
        r"\[([^\]]+)\]\(([^\)]+)\)",
        r'<link href="\2" color="#e8400c">\1</link>',
        text
    )
    return text
