"""
Grievance360 - report layout engine.

Everything about how the PDF *looks* lives here: page size, margins, fonts,
heading styles, table styling. The content lives in generate_report.py.

Splitting them means you can restyle the whole document without touching a
single word of the report, and vice versa.
"""

import os

from fpdf import FPDF
from fpdf.enums import Align, XPos, YPos
from fpdf.fonts import FontFace

FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

# ---------------------------------------------------------------- design ----
# One place for every measurement, so the document stays consistent.
PAGE_W, PAGE_H = 210, 297           # A4 in mm
M_LEFT = M_RIGHT = 20               # side margins
M_TOP = 22
M_BOTTOM = 20
CONTENT_W = PAGE_W - M_LEFT - M_RIGHT       # 170 mm of usable width

NAVY = (30, 58, 95)
NAVY_LIGHT = (44, 82, 130)
GREY = (108, 117, 125)
LIGHT = (242, 245, 249)
RULE = (210, 216, 224)
GREEN = (25, 135, 84)
RED = (200, 45, 60)

SIZE_BODY = 10
SIZE_SMALL = 8.4
SIZE_H1 = 17
SIZE_H2 = 12.5
SIZE_H3 = 10.5
LH = 5.0                            # body line height in mm


class Report(FPDF):
    """FPDF subclass that paints the running header and footer."""

    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(M_LEFT, M_TOP, M_RIGHT)
        self.set_auto_page_break(True, margin=M_BOTTOM)
        self.chapter = ""
        self.plain = True           # True = no header/footer (cover, TOC)

        self.add_font("DJ", "", os.path.join(FONT_DIR, "DejaVuSans.ttf"))
        self.add_font("DJ", "B", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"))
        self.add_font("DJ", "I", os.path.join(FONT_DIR,
                                              "DejaVuSans-Oblique.ttf"))
        self.add_font("DJM", "", os.path.join(FONT_DIR, "DejaVuSansMono.ttf"))
        self.set_font("DJ", "", SIZE_BODY)

    def header(self):
        if self.plain:
            return
        self.set_y(11)
        self.set_font("DJ", "", 8)
        self.set_text_color(*GREY)
        self.cell(CONTENT_W * 0.55, 4, "Grievance360 - Project Report",
                  align=Align.L)
        self.cell(CONTENT_W * 0.45, 4, self.chapter, align=Align.R,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.line(M_LEFT, 17, PAGE_W - M_RIGHT, 17)
        self.set_text_color(0, 0, 0)

    def footer(self):
        if self.plain:
            return
        self.set_y(-15)
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.line(M_LEFT, PAGE_H - 17, PAGE_W - M_RIGHT, PAGE_H - 17)
        self.set_font("DJ", "", 8)
        self.set_text_color(*GREY)
        self.cell(CONTENT_W, 5, "Page " + str(self.page_no()), align=Align.C)
        self.set_text_color(0, 0, 0)


# ---------------------------------------------------------------------------
# Content helpers. Each one leaves the cursor at the left margin on a new
# line, so sections can simply be called one after another.
# ---------------------------------------------------------------------------
class Writer:
    def __init__(self, pdf):
        self.pdf = pdf

    # -- structure ---------------------------------------------------------
    def h1(self, text):
        """Chapter heading - always starts a fresh page."""
        pdf = self.pdf
        pdf.plain = False
        # The chapter name must be set BEFORE add_page, because add_page
        # triggers header() immediately - setting it afterwards would print
        # the previous chapter's name at the top of this one.
        pdf.chapter = text
        pdf.add_page()
        pdf.start_section(text, level=0)
        pdf.set_font("DJ", "B", SIZE_H1)
        pdf.set_text_color(*NAVY)
        pdf.multi_cell(CONTENT_W, 8.5, text,
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        y = pdf.get_y() + 1
        pdf.set_draw_color(*NAVY)
        pdf.set_line_width(0.7)
        pdf.line(M_LEFT, y, M_LEFT + 30, y)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(6)

    def h2(self, text, needs=34):
        """`needs` reserves room for the heading plus the first few lines of
        whatever follows, so a heading is never stranded at a page foot."""
        pdf = self.pdf
        self.keep(needs)
        pdf.start_section(text, level=1)
        pdf.set_font("DJ", "B", SIZE_H2)
        pdf.set_text_color(*NAVY_LIGHT)
        pdf.multi_cell(CONTENT_W, 6, text,
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1.5)

    def h3(self, text, needs=30):
        pdf = self.pdf
        self.keep(needs)
        pdf.set_font("DJ", "B", SIZE_H3)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(CONTENT_W, 5.4, text,
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

    # -- text --------------------------------------------------------------
    def body(self, text, align=Align.J):
        """Justified paragraph - Align.J is what gives even side margins."""
        pdf = self.pdf
        pdf.set_font("DJ", "", SIZE_BODY)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(CONTENT_W, LH, text, align=align,
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2.6)

    def bullets(self, items, indent=4):
        pdf = self.pdf
        pdf.set_font("DJ", "", SIZE_BODY)
        pdf.set_text_color(0, 0, 0)
        for item in items:
            self.keep(LH * 2)
            pdf.set_x(M_LEFT + indent)
            pdf.cell(4.5, LH, chr(0x2022))
            pdf.set_x(M_LEFT + indent + 4.5)
            pdf.multi_cell(CONTENT_W - indent - 4.5, LH, item, align=Align.J,
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2.6)

    def numbered(self, items, indent=4):
        pdf = self.pdf
        pdf.set_font("DJ", "", SIZE_BODY)
        pdf.set_text_color(0, 0, 0)
        for number, item in enumerate(items, 1):
            self.keep(LH * 2)
            pdf.set_x(M_LEFT + indent)
            pdf.cell(6.5, LH, str(number) + ".")
            pdf.set_x(M_LEFT + indent + 6.5)
            pdf.multi_cell(CONTENT_W - indent - 6.5, LH, item, align=Align.J,
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2.6)

    def code(self, lines):
        """Monospaced block on a tinted background."""
        pdf = self.pdf
        height = 4.4 * len(lines) + 5
        self.keep(height + 4)
        top = pdf.get_y()
        pdf.set_fill_color(*LIGHT)
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.2)
        pdf.rect(M_LEFT, top, CONTENT_W, height, style="DF")
        pdf.set_font("DJM", "", 8.2)
        pdf.set_text_color(0, 0, 0)
        pdf.set_y(top + 2.5)
        for line in lines:
            pdf.set_x(M_LEFT + 4)
            pdf.cell(CONTENT_W - 8, 4.4, line,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_y(top + height)
        pdf.ln(4)
        pdf.set_font("DJ", "", SIZE_BODY)

    def callout(self, title, text, colour=None):
        """Boxed note with a coloured left rule."""
        pdf = self.pdf
        colour = colour or NAVY_LIGHT
        inner = CONTENT_W - 11
        pdf.set_font("DJ", "", SIZE_SMALL)
        lines = pdf.multi_cell(inner, 4.4, text, dry_run=True,
                               output="LINES", align=Align.J)
        height = 4.4 * (len(lines) + 1) + 7
        self.keep(height + 4)
        top = pdf.get_y()
        pdf.set_fill_color(*LIGHT)
        pdf.rect(M_LEFT, top, CONTENT_W, height, style="F")
        pdf.set_fill_color(*colour)
        pdf.rect(M_LEFT, top, 1.8, height, style="F")
        pdf.set_xy(M_LEFT + 7, top + 3)
        pdf.set_font("DJ", "B", SIZE_SMALL)
        pdf.set_text_color(*colour)
        pdf.cell(inner, 4.4, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_x(M_LEFT + 7)
        pdf.set_font("DJ", "", SIZE_SMALL)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(inner, 4.4, text, align=Align.J,
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_y(top + height)
        pdf.ln(3.5)
        pdf.set_font("DJ", "", SIZE_BODY)

    # -- tables ------------------------------------------------------------
    def table(self, headings, rows, widths, aligns=None, size=SIZE_SMALL):
        """
        Fixed-width table.

        `widths` are fractions of CONTENT_W, so every table in the document
        starts and ends on exactly the same left and right edge as the body
        text. That single rule is what makes the pages look aligned.
        """
        pdf = self.pdf
        total = sum(widths)
        col_widths = tuple(w / total * CONTENT_W for w in widths)
        aligns = tuple(aligns or ["LEFT"] * len(headings))
        pdf.set_font("DJ", "", size)
        pdf.set_text_color(0, 0, 0)
        # Row striping uses the document's CURRENT fill colour, so it must be
        # reset here. Without this a table placed after a callout or a chart
        # tile inherits that element's dark fill and stripes rows in navy with
        # black text on top - unreadable.
        pdf.set_fill_color(*LIGHT)
        pdf.set_draw_color(*RULE)
        heading_style = FontFace(emphasis="BOLD", color=(255, 255, 255),
                                 fill_color=NAVY)
        with pdf.table(col_widths=col_widths,
                       text_align=aligns,
                       headings_style=heading_style,
                       line_height=4.5,
                       cell_fill_color=LIGHT,
                       cell_fill_mode="ROWS",
                       borders_layout="SINGLE_TOP_LINE",
                       width=CONTENT_W,
                       align=Align.L,
                       padding=(1.3, 1.8, 1.3, 1.8)) as tbl:
            head = tbl.row()
            for text in headings:
                head.cell(str(text))
            for row in rows:
                line = tbl.row()
                for text in row:
                    line.cell(str(text))
        pdf.ln(4)
        pdf.set_font("DJ", "", SIZE_BODY)

    def metrics(self, items):
        """A row of big-number tiles, evenly divided across the text width."""
        pdf = self.pdf
        self.keep(24)
        count = len(items)
        gap = 4
        width = (CONTENT_W - gap * (count - 1)) / count
        top = pdf.get_y()
        for index, (value, label, colour) in enumerate(items):
            x = M_LEFT + index * (width + gap)
            pdf.set_fill_color(*LIGHT)
            pdf.rect(x, top, width, 19, style="F")
            pdf.set_xy(x, top + 3)
            pdf.set_font("DJ", "B", 15)
            pdf.set_text_color(*colour)
            pdf.cell(width, 8, str(value), align=Align.C)
            pdf.set_xy(x, top + 11.5)
            pdf.set_font("DJ", "", 7.5)
            pdf.set_text_color(*GREY)
            pdf.cell(width, 4, label.upper(), align=Align.C)
        pdf.set_y(top + 19)
        pdf.ln(6)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("DJ", "", SIZE_BODY)

    # -- utility -----------------------------------------------------------
    def keep(self, height):
        """Move to the next page if `height` mm will not fit - kills orphans."""
        if self.pdf.get_y() + height > PAGE_H - M_BOTTOM:
            self.pdf.add_page()

    def space(self, amount=3):
        self.pdf.ln(amount)
