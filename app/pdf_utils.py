import io
from datetime import datetime, timezone
from flask import Response
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print 'Page X of Y' in the footer."""
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
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Footer line
        width, height = self._pagesize
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.75)
        self.line(36, 32, width - 36, 32)

        # Footer text
        footer_text = "StockPulse — Inventory & Stock Analysis System"
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawString(36, 20, footer_text)
        self.drawRightString(width - 36, 20, page_str)

        self.restoreState()


def build_pdf_document(
    title: str,
    subtitle: str,
    headers: list,
    data_rows: list,
    col_widths: list = None,
    orientation: str = "portrait"
) -> bytes:
    """
    Renders a clean, enterprise-grade PDF table report using ReportLab.
    """
    buffer = io.BytesIO()
    page_size = landscape(letter) if orientation == "landscape" else letter
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=36,
        rightMargin=36,
        topMargin=40,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()

    # Title style
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2
    )

    # Subtitle / metadata style
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=14
    )

    # Table cell normal style
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1e293b")
    )

    # Table header style
    header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    elements = []

    # Document Header
    now_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"{subtitle} &bull; Generated on: {now_str} &bull; Total Records: {len(data_rows)}", subtitle_style))

    # Format table data with Paragraphs to support auto word-wrapping
    formatted_table_data = []
    
    # Headers
    header_cells = [Paragraph(str(h), header_style) for h in headers]
    formatted_table_data.append(header_cells)

    # Rows
    for row in data_rows:
        row_cells = []
        for cell in row:
            text = str(cell) if cell is not None else ""
            row_cells.append(Paragraph(text, cell_style))
        formatted_table_data.append(row_cells)

    # Table styling
    t = Table(formatted_table_data, colWidths=col_widths, repeatRows=1)
    
    table_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]

    # Alternating row background
    for i in range(1, len(formatted_table_data)):
        bg_color = colors.HexColor("#f8fafc") if i % 2 == 1 else colors.white
        table_styles.append(("BACKGROUND", (0, i), (-1, i), bg_color))

    t.setStyle(TableStyle(table_styles))
    elements.append(t)

    # Build PDF
    doc.build(elements, canvasmaker=NumberedCanvas)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data


def generate_pdf_response(
    title: str,
    subtitle: str,
    headers: list,
    data_rows: list,
    filename: str,
    col_widths: list = None,
    orientation: str = "portrait"
) -> Response:
    """Creates a Flask HTTP Response delivering an attachment PDF."""
    pdf_bytes = build_pdf_document(
        title=title,
        subtitle=subtitle,
        headers=headers,
        data_rows=data_rows,
        col_widths=col_widths,
        orientation=orientation
    )

    response = Response(pdf_bytes, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
