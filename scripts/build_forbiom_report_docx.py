"""Build the FORBIOM-ON preliminary results report as a polished DOCX."""
import csv
import math
import os
import re

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Pt, Inches, RGBColor, Twips

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "_report_build")
OUT = os.path.join(HERE, "FORBIOM-ON_Preliminary_Results_Report_v3.docx")
os.makedirs(BUILD, exist_ok=True)

FOREST = "1B4332"
PINE = "2D6A4F"
SAGE = "E8F0EA"
MIST = "F4F8F5"
GOLD = "C9A227"
GOLD_LIGHT = "FBF6E9"
INK = "1F2A24"
GREY = "5F6B64"
RULE = "A9C5B1"

BODY_FONT = "Calibri"
HEAD_FONT = "Georgia"
DATE_TEXT = "October 15, 2026"
DRIVE_URL = "https://drive.google.com/drive/folders/1BEIqHIwqxvgYLBW9_R_Qtkq_qobNHUVA?usp=sharing"
# Filled after `gh repo create` (override with env FORBIOM_GITHUB_URL if needed).
GITHUB_URL = os.environ.get(
    "FORBIOM_GITHUB_URL",
    "https://github.com/yassirelfahli/forbiom-on",
)
PLONSKI_URL = "https://web.archive.org/web/20070811162227/http://flash.lakeheadu.ca/%7Efluckai/nytweb.html"


def rgb(hex_):
    return RGBColor.from_string(hex_)


# --------------------------------------------------------------------------
# Placeholder pictures (replace via right-click > Change Picture in Word)
# --------------------------------------------------------------------------
def _font(name, size):
    try:
        return ImageFont.truetype(os.path.join(r"C:\Windows\Fonts", name), size)
    except OSError:
        return ImageFont.load_default()


def make_placeholder(path, w, h, title, hint, scale=1.0):
    img = Image.new("RGB", (w, h), "#E8F0EA")
    d = ImageDraw.Draw(img)
    top, bot = (0xEE, 0xF4, 0xEF), (0xD5, 0xE5, 0xD9)
    for y in range(h):
        t = y / max(h - 1, 1)
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))

    pad = int(28 * scale)
    dash, gap, lw = int(26 * scale), int(16 * scale), max(3, int(5 * scale))
    col = (0x2D, 0x6A, 0x4F)
    for x0 in range(pad, w - pad, dash + gap):
        x1 = min(x0 + dash, w - pad)
        d.line([(x0, pad), (x1, pad)], fill=col, width=lw)
        d.line([(x0, h - pad), (x1, h - pad)], fill=col, width=lw)
    for y0 in range(pad, h - pad, dash + gap):
        y1 = min(y0 + dash, h - pad)
        d.line([(pad, y0), (pad, y1)], fill=col, width=lw)
        d.line([(w - pad, y0), (w - pad, y1)], fill=col, width=lw)

    cx, cy = w // 2, int(h * 0.40)
    s = int(min(w, h) * 0.16)
    d.ellipse([cx + s * 0.35, cy - s * 0.95, cx + s * 0.85, cy - s * 0.45], fill=(0xC9, 0xA2, 0x27))
    d.polygon([(cx - s * 1.3, cy + s * 0.6), (cx - s * 0.35, cy - s * 0.55), (cx + s * 0.45, cy + s * 0.6)],
              fill=(0x2D, 0x6A, 0x4F))
    d.polygon([(cx - s * 0.2, cy + s * 0.6), (cx + s * 0.55, cy - s * 0.2), (cx + s * 1.3, cy + s * 0.6)],
              fill=(0x1B, 0x43, 0x32))

    f1 = _font("segoeuib.ttf", int(min(w, h) * 0.085))
    f2 = _font("segoeui.ttf", int(min(w, h) * 0.05))
    ty = cy + int(s * 0.95)
    tw = d.textlength(title, font=f1)
    d.text((cx - tw / 2, ty), title, font=f1, fill=(0x1B, 0x43, 0x32))
    hw = d.textlength(hint, font=f2)
    d.text((cx - hw / 2, ty + int(min(w, h) * 0.11)), hint, font=f2, fill=(0x5F, 0x6B, 0x64))
    img.save(path, dpi=(300, 300))
    return path


PH_HERO = make_placeholder(os.path.join(BUILD, "ph_cover_main.png"), 1620, 885,
                           "COVER IMAGE", "Right-click  >  Change Picture  to insert", 1.2)
PH_SIDE_A = make_placeholder(os.path.join(BUILD, "ph_cover_2.png"), 900, 540,
                             "PICTURE 2", "Right-click > Change Picture", 0.7)
PH_SIDE_B = make_placeholder(os.path.join(BUILD, "ph_cover_3.png"), 900, 540,
                             "PICTURE 3", "Right-click > Change Picture", 0.7)
PH_LOGO = make_placeholder(os.path.join(BUILD, "ph_logo.png"), 900, 330,
                           "LOGO", "Right-click > Change Picture", 0.5)


def make_workflow(path):
    """Two-pipeline data-processing diagram (ABM left, FORBIOM-ON right)."""
    W = 1950
    label_w, gap, margin = 250, 60, 20
    col_w = (W - 2 * margin - label_w - gap - 20) // 2
    x_lab = margin
    x_a = margin + label_w + 20
    x_b = x_a + col_w + gap
    f_head = _font("segoeuib.ttf", 37)
    f_lab = _font("segoeuib.ttf", 33)
    f_tit = _font("segoeuib.ttf", 31)
    f_txt = _font("segoeui.ttf", 29)
    green, pine, gold = (0x1B, 0x43, 0x32), (0x2D, 0x6A, 0x4F), (0xC9, 0xA2, 0x27)
    ink, grey = (0x1F, 0x2A, 0x24), (0x5F, 0x6B, 0x64)
    fills = [(0xF4, 0xF8, 0xF5), (0xE8, 0xF0, 0xEA), (0xFB, 0xF6, 0xE9), (0xE3, 0xEE, 0xE6), (0xF4, 0xF8, 0xF5)]

    rows = [
        ("1  Raw data",
         ("ARWoodS 2025 extract (MNR)", ["LTMD and actual harvest, merchantable volume,", "FY2019\u20132024, by FMU and species group",
                                         "eFAR summary (MNR, Sept. 2024):", "employees, roundwood use, FMU deliveries 2020\u201322"]),
         ("Inventory, yield and market data", ["Plonski yield tables (GMV, m\u00B3/ha by age)", "GeoHub regional roundwood stocks",
                                               "FRI FIM v2 geodatabases (six FMUs)", "Prices, costs, demand caps, carbon factors"])),
        ("2  Processing",
         ("calibrate.py", ["Filter six MUs, FT = Merch, FY2019\u20132024", "Map SPF/PWR/OC/CE \u2192 SW; PO \u2192 PO; BW/TOL \u2192 HW",
                           "Six-year annual means; utilization = harvest/LTMD", "eFAR: jobs per 1,000 m\u00B3 by facility type"]),
         ("GAMS data block  +  process_fri_data.py", ["Site-class and species yield proxies",
                                                     "FMU area and CAI inferred from yield curves",
                                                     "Price (+3%/yr) and cost (\u22122%/yr) paths; seeded shocks",
                                                     "FRI: harmonize, reproject (EPSG:3347), aggregate"])),
        ("3  Model inputs",
         ("Calibration tables", ["regions.csv (LTMD, harvest by fibre)", "efar_jobs.csv, efar_fmu_flows.csv",
                                 "BASE_PARAMS (prices, technologies, behaviour)"]),
         ("GAMS parameters", ["Initial stock, CAI growth, species mix",
                              "Demand caps, transport matrix, capacities", "Emission and storage factors"])),
        ("4  Models",
         ("FORBIOM-ABM simulation", ["6 FMU managers, 60 contractors, 51 incumbent", "mills, entrant plants; annual steps 2026\u20132045",
                                     "Logistic decisions, adaptive expectations"]),
         ("FORBIOM-ON optimization (NLP)", ["6 FMUs \u00D7 4 products \u00D7 11 years (2020\u20132030)",
                                     "Max. net value incl. carbon cost", "Arc, mill and sustainability constraints"])),
        ("5  Outputs",
         ("Monte Carlo results", ["2,310 runs (+930 tuning runs)", "Time series, plant registry, MCDA scores"]),
         ("GDX \u2192 CSV tables", ["Harvest, production, revenue, carbon", "Carbon-price and demand sweeps"])),
    ]

    def wrap_h(title, lines):
        return 26 + 40 + 8 + len(lines) * 38 + 22

    heights = [max(wrap_h(*a), wrap_h(*b)) for _, a, b in rows]
    head_h, row_gap = 80, 46
    H = margin + head_h + 20 + sum(heights) + row_gap * (len(rows) - 1) + 220
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    for x, txt in ((x_a, "FORBIOM-ABM pipeline (Python)"), (x_b, "FORBIOM-ON pipeline (GAMS)")):
        d.rounded_rectangle([x, margin, x + col_w, margin + head_h], 14, fill=green)
        tw = d.textlength(txt, font=f_head)
        d.text((x + (col_w - tw) / 2, margin + 16), txt, font=f_head, fill="white")

    y = margin + head_h + 20
    centers = []
    for i, (lab, a, b) in enumerate(rows):
        h = heights[i]
        d.rounded_rectangle([x_lab, y, x_lab + label_w, y + h], 12, fill=gold if i == 3 else pine)
        lines = lab.split("  ")
        ty = y + h / 2 - 40
        d.text((x_lab + 22, ty), lines[0], font=_font("segoeuib.ttf", 48), fill="white")
        d.text((x_lab + 22, ty + 50), lines[1], font=f_lab, fill="white")
        for x, (title, txt_lines) in ((x_a, a), (x_b, b)):
            d.rounded_rectangle([x, y, x + col_w, y + h], 14, fill=fills[i], outline=pine, width=3)
            d.text((x + 26, y + 22), title, font=f_tit, fill=green)
            for k, line in enumerate(txt_lines):
                d.text((x + 26, y + 22 + 46 + k * 38), "\u2022  " + line, font=f_txt, fill=ink)
        centers.append((y, y + h))
        if i < len(rows) - 1:
            for x in (x_a, x_b):
                cx = x + col_w // 2
                y0, y1 = y + h + 6, y + h + row_gap - 6
                d.line([(cx, y0), (cx, y1 - 14)], fill=pine, width=6)
                d.polygon([(cx - 16, y1 - 18), (cx + 16, y1 - 18), (cx, y1)], fill=pine)
        y += h + row_gap

    my0, my1 = centers[3]
    mid_y = (my0 + my1) // 2
    xa_r, xb_l = x_a + col_w + 6, x_b - 6
    for xx in range(xa_r, xb_l, 14):
        d.line([(xx, mid_y), (min(xx + 8, xb_l), mid_y)], fill=gold, width=6)
    d.polygon([(xb_l, mid_y), (xb_l - 16, mid_y - 12), (xb_l - 16, mid_y + 12)], fill=gold)
    d.polygon([(xa_r, mid_y), (xa_r + 16, mid_y - 12), (xa_r + 16, mid_y + 12)], fill=gold)

    note = ("Shared by both models: six FMU regions  \u00B7  harvest cost $38/m\u00B3  \u00B7  "
            "1.20 m\u00B3 lumber per m\u00B3 CLT  \u00B7  carbon factors")
    nb = y - row_gap + 30
    d.rounded_rectangle([x_a, nb, x_b + col_w, nb + 70], 12, fill=(0xFB, 0xF6, 0xE9), outline=gold, width=3)
    tw = d.textlength(note, font=f_txt)
    d.text((x_a + (x_b + col_w - x_a - tw) / 2, nb + 18), note, font=f_txt, fill=ink)
    leg = "\u2194  dashed gold arrow: planned co-evolutionary coupling (harvest intensity, adoption rates \u2194 shadow prices, policy signals)"
    tw = d.textlength(leg, font=_font("segoeui.ttf", 26))
    d.text(((W - tw) / 2, nb + 84), leg, font=_font("segoeui.ttf", 26), fill=grey)
    img = img.crop((0, 0, W, nb + 124))
    img.save(path, dpi=(300, 300))
    return path


WORKFLOW = make_workflow(os.path.join(BUILD, "data_workflow.png"))


# --------------------------------------------------------------------------
# Low-level XML helpers
# --------------------------------------------------------------------------
def _get_or_add(parent, tag):
    el = parent.find(qn(tag))
    if el is None:
        el = OxmlElement(tag)
        parent.append(el)
    return el


def set_cell_bg(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:shd")):
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def set_cell_borders(cell, **edges):
    """edges: top/bottom/left/right = (sz, color) or None for 'nil'."""
    tcPr = cell._tc.get_or_add_tcPr()
    borders = _get_or_add(tcPr, "w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        if edge not in edges:
            continue
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        spec = edges[edge]
        if spec is None:
            el.set(qn("w:val"), "nil")
        else:
            sz, color = spec[0], spec[1]
            val = spec[2] if len(spec) > 2 else "single"
            el.set(qn("w:val"), val)
            el.set(qn("w:sz"), str(sz))
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), color)
    order = ["top", "left", "bottom", "right"]
    kids = sorted(list(borders), key=lambda e: order.index(e.tag.split("}")[1]))
    for k in kids:
        borders.remove(k)
        borders.append(k)


def set_cell_margins(cell, top=None, bottom=None, left=None, right=None):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = _get_or_add(tcPr, "w:tcMar")
    for side, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        if val is None:
            continue
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)


def set_table_borders(table, **edges):
    tblPr = table._tbl.tblPr
    borders = _get_or_add(tblPr, "w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        spec = edges.get(edge)
        if spec is None:
            el.set(qn("w:val"), "nil")
        else:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(spec[0]))
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), spec[1])
        borders.append(el)


def set_table_cell_margins(table, top=25, bottom=25, left=70, right=70):
    tblPr = table._tbl.tblPr
    mar = _get_or_add(tblPr, "w:tblCellMar")
    for side, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)


def set_col_widths(table, widths_in):
    table.autofit = False
    tblPr = table._tbl.tblPr
    layout = _get_or_add(tblPr, "w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblW = _get_or_add(tblPr, "w:tblW")
    tblW.set(qn("w:w"), str(int(sum(widths_in) * 1440)))
    tblW.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for i, gc in enumerate(grid.findall(qn("w:gridCol"))):
        gc.set(qn("w:w"), str(int(widths_in[i] * 1440)))
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            if i < len(widths_in):
                cell.width = Inches(widths_in[i])


def mark_header_row(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def cant_split(row):
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))


def para_border(p, edge, sz, color, space=4):
    pPr = p._p.get_or_add_pPr()
    pbdr = _get_or_add(pPr, "w:pBdr")
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:space"), str(space))
    el.set(qn("w:color"), color)
    pbdr.append(el)


def tiny_mark(p, half_points=2):
    pPr = p._p.get_or_add_pPr()
    rPr = _get_or_add(pPr, "w:rPr")
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(half_points))
    rPr.append(sz)


def char_spacing(run, twips):
    rPr = run._r.get_or_add_rPr()
    sp = OxmlElement("w:spacing")
    sp.set(qn("w:val"), str(twips))
    rPr.append(sp)


def set_run_font(run, name):
    run.font.name = name
    rFonts = run._r.get_or_add_rPr().find(qn("w:rFonts"))
    rFonts.set(qn("w:eastAsia"), name)
    rFonts.set(qn("w:cs"), name)


def fmt_run(run, size=None, color=None, bold=None, italic=None, font=None):
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = rgb(color)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if font is not None:
        set_run_font(run, font)
    return run


def pfmt(p, before=None, after=None, line=None, align=None, keep_next=None, left=None, first=None):
    pf = p.paragraph_format
    if before is not None:
        pf.space_before = Pt(before)
    if after is not None:
        pf.space_after = Pt(after)
    if line is not None:
        pf.line_spacing = line
    if align is not None:
        pf.alignment = align
    if keep_next is not None:
        pf.keep_with_next = keep_next
    if left is not None:
        pf.left_indent = Inches(left)
    if first is not None:
        pf.first_line_indent = Inches(first)
    return p


def add_field(p, instr, cached, **fmt):
    def mk(child):
        r = p.add_run()
        fmt_run(r, **fmt)
        r._r.append(child)
        return r

    b = OxmlElement("w:fldChar")
    b.set(qn("w:fldCharType"), "begin")
    mk(b)
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    mk(it)
    s = OxmlElement("w:fldChar")
    s.set(qn("w:fldCharType"), "separate")
    mk(s)
    fmt_run(p.add_run(cached), **fmt)
    e = OxmlElement("w:fldChar")
    e.set(qn("w:fldCharType"), "end")
    mk(e)


def add_hyperlink(p, text, url, bold=False, size=None, color=PINE):
    r_id = p.part.relate_to(url, RT.HYPERLINK, is_external=True)
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), r_id)
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color)
    rPr.append(c)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)
    if bold:
        rPr.append(OxmlElement("w:b"))
    if size:
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(size * 2)))
        rPr.append(sz)
    r.append(rPr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    h.append(r)
    p._p.append(h)


TOKEN = re.compile(r"(\[[^\]]+\]\([^)]+\)|\*\*.+?\*\*|\*.+?\*|\^\{.+?\}|~\{.+?\}|`.+?`)")


def add_rich(p, text, size=None, color=None, bold=False, italic=False, font=None):
    """Mini markup: **bold**, *italic*, ^{sup}, ~{sub}, `mono`, [text](url)."""
    for part in TOKEN.split(text):
        if not part:
            continue
        b, i, sup, sub, mono = bold, italic, False, False, False
        if part.startswith("[") and "](" in part:
            label, url = part[1:].split("](", 1)
            url = url[:-1]
            lb = label.startswith("**")
            add_hyperlink(p, label.strip("*"), url, bold=lb or bold, size=size)
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            part, b = part[2:-2], True
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            part, i = part[1:-1], not italic
        elif part.startswith("^{"):
            part, sup = part[2:-1], True
        elif part.startswith("~{"):
            part, sub = part[2:-1], True
        elif part.startswith("`"):
            part, mono = part[1:-1], True
        r = p.add_run(part)
        fmt_run(r, size=size, color=color, bold=b or None, italic=i or None, font="Consolas" if mono else font)
        if sup:
            r.font.superscript = True
        if sub:
            r.font.subscript = True
    return p


# --------------------------------------------------------------------------
# Document + styles
# --------------------------------------------------------------------------
doc = Document()
doc.core_properties.title = "Ontario Forest Biomass: Supply Chain Feasibility, Processing Optimization, and ABM-Integrated Biomass Utilization"
doc.core_properties.subject = "FORBIOM-ON preliminary results"
doc.core_properties.author = "Rasoul Yousefpour; Yasser Elfahli"
doc.core_properties.keywords = "FORBIOM-ON, Ontario, forest biomass, GAMS, agent-based model, mass timber"


def style_font(style, name, size=None, color=None, bold=None, italic=None):
    style.font.name = name
    rPr = style.element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rFonts.get(qn(attr)) is not None:
            del rFonts.attrib[qn(attr)]
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rFonts.set(qn(attr), name)
    if size:
        style.font.size = Pt(size)
    if color:
        style.font.color.rgb = rgb(color)
        c = rPr.find(qn("w:color"))
        for attr in ("w:themeColor", "w:themeShade", "w:themeTint"):
            if c.get(qn(attr)) is not None:
                del c.attrib[qn(attr)]
    if bold is not None:
        style.font.bold = bold
    if italic is not None:
        style.font.italic = italic


normal = doc.styles["Normal"]
style_font(normal, BODY_FONT, 11, INK)
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.15

h1 = doc.styles["Heading 1"]
style_font(h1, HEAD_FONT, 17, FOREST, bold=True)
h1.paragraph_format.space_before = Pt(20)
h1.paragraph_format.space_after = Pt(10)
h1.paragraph_format.keep_with_next = True
h1_pPr = h1.element.get_or_add_pPr()
_b = OxmlElement("w:pBdr")
_bb = OxmlElement("w:bottom")
for k, v in (("w:val", "single"), ("w:sz", "8"), ("w:space", "4"), ("w:color", GOLD)):
    _bb.set(qn(k), v)
_b.append(_bb)
h1_pPr.append(_b)

h2 = doc.styles["Heading 2"]
style_font(h2, HEAD_FONT, 12.5, PINE, bold=True)
h2.paragraph_format.space_before = Pt(12)
h2.paragraph_format.space_after = Pt(4)
h2.paragraph_format.keep_with_next = True

for lvl, size in (("TOC 1", 11), ("TOC 2", 10.5)):
    try:
        st = doc.styles[lvl]
    except KeyError:
        from docx.enum.style import WD_STYLE_TYPE
        st = doc.styles.add_style(lvl, WD_STYLE_TYPE.PARAGRAPH)
    style_font(st, BODY_FONT, size, FOREST if lvl == "TOC 1" else INK, bold=(lvl == "TOC 1"))
    st.paragraph_format.space_before = Pt(6 if lvl == "TOC 1" else 1)
    st.paragraph_format.space_after = Pt(2)
    if lvl == "TOC 2":
        st.paragraph_format.left_indent = Inches(0.3)


def body(text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, **kw):
    p = doc.add_paragraph()
    pfmt(p, align=align)
    add_rich(p, text, **kw)
    return p


def heading1(num, text):
    p = doc.add_paragraph(style="Heading 1")
    if num:
        fmt_run(p.add_run(f"{num}"), color=GOLD)
        p.add_run("  ")
    p.add_run(text)
    return p


def heading2(text, num=None):
    p = doc.add_paragraph(style="Heading 2")
    if num:
        fmt_run(p.add_run(num), color=GOLD)
        p.add_run("  ")
    p.add_run(text)
    return p


def heading3(text):
    p = doc.add_paragraph()
    pfmt(p, before=8, after=2, keep_next=True)
    fmt_run(p.add_run(text), size=11, color=FOREST, bold=True, italic=True, font=HEAD_FONT)
    return p


MNS = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'


def mt(t, plain=False):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    sty = '<m:rPr><m:sty m:val="p"/></m:rPr>' if plain else ""
    return f'<m:r>{sty}<m:t xml:space="preserve">{t}</m:t></m:r>'


def msub(b, s):
    return f"<m:sSub><m:e>{b}</m:e><m:sub>{s}</m:sub></m:sSub>"


def msup(b, s):
    return f"<m:sSup><m:e>{b}</m:e><m:sup>{s}</m:sup></m:sSup>"


def msubsup(b, sb, sp):
    return f"<m:sSubSup><m:e>{b}</m:e><m:sub>{sb}</m:sub><m:sup>{sp}</m:sup></m:sSubSup>"


def mfrac(n, d):
    return f"<m:f><m:num>{n}</m:num><m:den>{d}</m:den></m:f>"


def mpar(x, left="(", right=")"):
    return (f'<m:d><m:dPr><m:begChr m:val="{left}"/><m:endChr m:val="{right}"/></m:dPr>'
            f"<m:e>{x}</m:e></m:d>")


def msum(sub, body):
    return (f'<m:nary><m:naryPr><m:chr m:val="\u2211"/><m:limLoc m:val="undOvr"/><m:supHide m:val="1"/>'
            f"</m:naryPr><m:sub>{sub}</m:sub><m:sup/><m:e>{body}</m:e></m:nary>")


def mover_bar(letter):
    return f'<m:bar><m:barPr><m:pos m:val="top"/></m:barPr><m:e>{mt(letter)}</m:e></m:bar>'


def msqrt(x):
    return f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>{x}</m:e></m:rad>'


def equation(xml):
    p = doc.add_paragraph()
    pfmt(p, before=4, after=6, align=WD_ALIGN_PARAGRAPH.CENTER)
    p._p.append(parse_xml(f"<m:oMathPara {MNS}><m:oMath>{xml}</m:oMath></m:oMathPara>"))
    return p


def bullet(text, level=0, container=None):
    p = (container or doc).add_paragraph()
    pfmt(p, after=3, left=0.28 + 0.25 * level, first=-0.18, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    fmt_run(p.add_run("\u25A0"), size=6.5, color=GOLD)
    p.add_run("\t")
    add_rich(p, text)
    return p


def enum_item(label, text):
    p = doc.add_paragraph()
    pfmt(p, after=3, left=0.42, first=-0.32, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    fmt_run(p.add_run(f"({label})"), color=PINE, bold=True)
    p.add_run("\t")
    p.paragraph_format.tab_stops.add_tab_stop(Inches(0.42))
    add_rich(p, text)
    return p


SEQ = {"Table": 0, "Figure": 0}


def caption(kind, text, container=None, align=WD_ALIGN_PARAGRAPH.LEFT, keep_next=False, new_page=False):
    SEQ[kind] += 1
    p = (container or doc).add_paragraph()
    pfmt(p, before=4 if kind == "Figure" else 10, after=6 if kind == "Figure" else 4,
         line=1.0, align=align, keep_next=keep_next)
    p.paragraph_format.page_break_before = new_page
    fmt_run(p.add_run(f"{kind} "), size=9.5, color=FOREST, bold=True)
    add_field(p, f"SEQ {kind} \\* ARABIC", str(SEQ[kind]), size=9.5, color=FOREST, bold=True)
    fmt_run(p.add_run(".\u2002"), size=9.5, color=FOREST, bold=True)
    add_rich(p, text, size=9.5, color=INK)
    return p


def notes(lines, container=None):
    for i, line in enumerate(lines):
        p = (container or doc).add_paragraph()
        pfmt(p, before=4 if i == 0 else 0, after=1, line=1.0, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
        add_rich(p, line, size=7.5, color=GREY)
    doc.paragraphs[-1].paragraph_format.space_after = Pt(10)


def figure(path, width_in, cap):
    p = doc.add_paragraph()
    pfmt(p, before=8, after=0, align=WD_ALIGN_PARAGRAPH.CENTER, keep_next=True, line=1.0)
    p.add_run().add_picture(path if os.path.exists(path) else PH_HERO, width=Inches(width_in))
    caption("Figure", cap, align=WD_ALIGN_PARAGRAPH.JUSTIFY)


def callout(fill=MIST, bar=GOLD, width_in=6.37):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(t)
    set_col_widths(t, [width_in])
    c = t.cell(0, 0)
    set_cell_bg(c, fill)
    set_cell_borders(c, left=(36, bar), top=None, bottom=None, right=None)
    set_cell_margins(c, top=220, bottom=200, left=300, right=300)
    return c


def header_footer(section, text_width_in):
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    section.header_distance = Inches(0.4)
    section.footer_distance = Inches(0.4)

    for el in section._sectPr.findall(qn("w:pgNumType")):
        section._sectPr.remove(el)

    hp = section.header.paragraphs[0]
    hp.text = ""
    pfmt(hp, after=0, line=1.0)
    for pos in (4680, 9360):
        hp.paragraph_format.tab_stops.add_tab_stop(Twips(pos), WD_TAB_ALIGNMENT.CLEAR)
    hp.paragraph_format.tab_stops.add_tab_stop(Inches(text_width_in), WD_TAB_ALIGNMENT.RIGHT)
    r = fmt_run(hp.add_run("FORBIOM-ON"), size=8.5, color=FOREST, bold=True)
    char_spacing(r, 30)
    fmt_run(hp.add_run("\tOntario Forest Biomass  \u00B7  Preliminary Results"), size=8.5, color=GREY)
    para_border(hp, "bottom", 6, GOLD, 4)

    fp = section.footer.paragraphs[0]
    fp.text = ""
    pfmt(fp, after=0, line=1.0)
    for pos in (4680, 9360):
        fp.paragraph_format.tab_stops.add_tab_stop(Twips(pos), WD_TAB_ALIGNMENT.CLEAR)
    fp.paragraph_format.tab_stops.add_tab_stop(Inches(text_width_in), WD_TAB_ALIGNMENT.RIGHT)
    para_border(fp, "top", 4, RULE, 4)
    fmt_run(fp.add_run("R. Yousefpour  \u00B7  Y. Elfahli"), size=8, color=GREY)
    fmt_run(fp.add_run("\t"), size=8.5)
    add_field(fp, "PAGE", "1", size=9, color=FOREST, bold=True)


# --------------------------------------------------------------------------
# COVER PAGE (own section, no header/footer)
# --------------------------------------------------------------------------
cov = doc.sections[0]
cov.page_width, cov.page_height = Inches(8.27), Inches(11.69)
for side in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
    setattr(cov, side, Inches(0.45))

COVER_W = 8.27 - 0.9
SIDEBAR, STRIP = 1.30, 0.09
CONTENT = COVER_W - SIDEBAR - STRIP

ct = doc.add_table(rows=1, cols=3)
set_table_borders(ct)
set_col_widths(ct, [SIDEBAR, STRIP, CONTENT])
row = ct.rows[0]
row.height = Twips(15200)
row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
side_c, strip_c, main_c = row.cells

set_cell_bg(side_c, FOREST)
set_cell_bg(strip_c, GOLD)
tcPr = side_c._tc.get_or_add_tcPr()
td = OxmlElement("w:textDirection")
td.set(qn("w:val"), "btLr")
tcPr.append(td)
side_c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
sp = side_c.paragraphs[0]
pfmt(sp, after=0, line=1.0, align=WD_ALIGN_PARAGRAPH.CENTER)
r = fmt_run(sp.add_run("FORBIOM"), size=46, color="FFFFFF", bold=True, font=HEAD_FONT)
char_spacing(r, 60)
r = fmt_run(sp.add_run("-ON"), size=46, color=GOLD, bold=True, font=HEAD_FONT)
char_spacing(r, 60)
r = fmt_run(sp.add_run("\u2003\u2003ONTARIO FOREST & WOOD SECTOR MODEL"), size=10.5, color="CFE1D5", font=BODY_FONT)
char_spacing(r, 50)

set_cell_margins(main_c, top=520, bottom=300, left=560, right=320)
main_c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

p = main_c.paragraphs[0]
pfmt(p, after=2, line=1.0)
r = fmt_run(p.add_run("PRELIMINARY RESULTS REPORT"), size=9.5, color=PINE, bold=True)
char_spacing(r, 50)
r = fmt_run(p.add_run("\u2002\u2002|\u2002\u2002" + DATE_TEXT.upper()), size=9.5, color=GOLD, bold=True)
char_spacing(r, 40)

p = main_c.add_paragraph()
pfmt(p, before=14, after=0, line=1.0)
p.add_run().add_picture(PH_HERO, width=Inches(5.3))

p = main_c.add_paragraph()
pfmt(p, before=26, after=0, line=0.95)
fmt_run(p.add_run("Ontario Forest Biomass"), size=32, color=FOREST, bold=True, font=HEAD_FONT)
p = main_c.add_paragraph()
pfmt(p, before=8, after=0, line=1.05)
fmt_run(p.add_run("Supply Chain Feasibility, Processing Optimization, and ABM-Integrated Biomass Utilization"),
        size=15.5, color=PINE, font=HEAD_FONT)

p = main_c.add_paragraph()
pfmt(p, before=14, after=0, line=1.0)
para_border(p, "top", 18, GOLD, 10)
fmt_run(p.add_run("Preliminary results  \u00B7  FORBIOM-ON spatial forest-sector model (2020\u20132030)"),
        size=11, color=GREY, italic=True)

p = main_c.add_paragraph()
pfmt(p, before=20, after=0, line=1.0)
p.add_run().add_picture(PH_SIDE_A, width=Inches(2.55))
p.add_run("\u2002")
p.add_run().add_picture(PH_SIDE_B, width=Inches(2.55))

inner = main_c.add_table(rows=1, cols=2)
set_table_borders(inner)
set_col_widths(inner, [3.0, 2.3])
a_c, l_c = inner.rows[0].cells
set_cell_margins(a_c, top=360, left=0, right=0)
set_cell_margins(l_c, top=420, left=0, right=0)
l_c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.BOTTOM
p = a_c.paragraphs[0]
pfmt(p, after=4, line=1.0)
r = fmt_run(p.add_run("PREPARED BY"), size=8.5, color=GOLD, bold=True)
char_spacing(r, 50)
for name in ("Rasoul Yousefpour", "Yasser Elfahli"):
    p = a_c.add_paragraph()
    pfmt(p, after=1, line=1.0)
    para_border(p, "left", 18, PINE, 8)
    fmt_run(p.add_run(name), size=13, color=FOREST, bold=True, font=HEAD_FONT)
p = a_c.add_paragraph()
pfmt(p, before=8, after=0, line=1.0)
fmt_run(p.add_run(DATE_TEXT), size=10, color=GREY)
p = l_c.paragraphs[0]
pfmt(p, after=0, line=1.0, align=WD_ALIGN_PARAGRAPH.RIGHT)
p.add_run().add_picture(PH_LOGO, width=Inches(2.1))
last = main_c.paragraphs[-1]
pfmt(last, after=0, line=1.0)
tiny_mark(last)

# --------------------------------------------------------------------------
# MAIN SECTION (portrait)
# --------------------------------------------------------------------------
main = doc.add_section(WD_SECTION.NEW_PAGE)
cover_break = doc.paragraphs[-1]
pfmt(cover_break, before=0, after=0, line=1.0)
tiny_mark(cover_break)
for side in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
    setattr(main, side, Inches(0.95))
TEXT_W = 8.27 - 1.9
header_footer(main, TEXT_W)
pg = OxmlElement("w:pgNumType")
pg.set(qn("w:start"), "1")
main._sectPr.append(pg)

# ---- Abstract ----
box = callout()
p = box.paragraphs[0]
pfmt(p, after=8, line=1.0)
r = fmt_run(p.add_run("ABSTRACT"), size=10, color=FOREST, bold=True)
char_spacing(r, 60)

ABSTRACT = [
    "This report presents the **preliminary results** from three core study streams: (*i*) a feasibility "
    "assessment of the forest biomass supply chain, covering sourcing locations, logistics, and material flows; "
    "(*ii*) a technical assessment of optimized biomass processing pathways and their economic sensitivities; and "
    "(*iii*) an agent-based modeling of biomass utilization patterns across Ontario\u2019s regions. To support these "
    "studies, we applied FORBIOM-ON, a dynamic spatial model of Ontario\u2019s forest sector, as the shared modeling "
    "framework across all three activity areas.",
    "FORBIOM-ON is a spatial, multi-commodity model for wood and wood-based products with a focus on Ontario\u2019s "
    "Forest Management Units (FMUs). It is designed to analyze the impacts of market developments and policy changes "
    "on forest management, wood processing industries, and regional wood product markets. The model represents the "
    "interactions between forest resources, industrial production, and inter-regional trade in major wood products, "
    "including lumber, pulpwood, and engineered wood. Implemented in GAMS and formulated as a nonlinear programming "
    "(NLP) problem, the model allows the analysis of how changes in market conditions, logistics constraints, "
    "industrial capacity, and carbon pricing influence harvest levels, production patterns, regional prices, and "
    "trade flows across the forest value chain. Preliminary simulations indicate that the model is able to capture "
    "regional developments in the Ontario forest sector and to evaluate the implications of policy and market "
    "changes for supply, demand, industrial production, and carbon outcomes.",
]
for txt in ABSTRACT:
    p = box.add_paragraph()
    pfmt(p, after=6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    add_rich(p, txt, size=10.5)
p = box.add_paragraph()
pfmt(p, before=4, after=0, line=1.0)
para_border(p, "top", 4, RULE, 6)
add_rich(p, f"Sections 5 and 6 document the data processing and the agent-based model; code, data and Appendix A are in the public GitHub repository ([link]({GITHUB_URL})).",
         size=8.5, color=GREY, italic=True)

# ---- Contents ----
p = doc.add_paragraph()
pfmt(p, before=26, after=8, keep_next=True)
fmt_run(p.add_run("Contents"), size=17, color=FOREST, bold=True, font=HEAD_FONT)
para_border(p, "bottom", 8, GOLD, 4)
p = doc.add_paragraph()
add_field(p, 'TOC \\o "1-2" \\h \\z \\u', "Right-click here and choose \u201CUpdate Field\u201D to build the table of contents.",
          color=GREY, italic=True)
doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

# ---- 1 Overview ----
heading1("1", "Overview")
body("Building on the three study streams outlined above, namely biomass supply chain feasibility, processing "
     "optimization, and biomass utilization, this section describes the structure and scope of the modeling framework "
     "used to support them. FORBIOM-ON is a regionalized economic simulation model designed to analyze the economic "
     "and environmental impacts of provincial policy shifts and market fluctuations on the forest industry and its "
     "related value chains in Ontario. It evaluates the trade-offs between biological forest preservation, industrial "
     "production, and carbon sequestration goals.")
body("The model is currently operational for a ten-year planning horizon (2020\u20132030) and integrates regional "
     "biophysical yield data with industrial capacity and logistics constraints across Northern and Southern Ontario. "
     "Structurally, it belongs to the class of spatial equilibrium and multi-commodity models. Its core features are:")
for t in [
    "**Recursive-dynamic with a yearly resolution**, where forest stock levels and available harvests in the current "
    "period are functionally dependent on the biological increment and extraction rates of previous years.",
    "**Distinction between seven tree species and site class** (Spruce, Jack Pine, White Birch, Tolerant Hardwoods, "
    "White Pine, Red Pine, and Aspen) and three site classes (SC1, SC2, SC3).",
    "**Manufacturing hierarchy disaggregated by layers**: Primary (Lumber, Pulpwood) and Secondary (CLT, Glulam), "
    "where secondary production is physically constrained by the mass-balance availability of regional lumber inputs.",
    f"**Supply-side differentiation based on** [**Plonski Yield Tables**]({PLONSKI_URL}), which drive species-specific "
    "Gross Merchantable Volume (m^{3}/ha) as a function of forest age and dominant site class.",
    "**Regionalized at the Forest Management Unit level** for six key Ontario regions: Trout Lake, Abitibi, Algoma, "
    "Kenora, Nipissing, and Algonquin.",
    "**Bilateral trade flows based on the Spatial Equilibrium concept**, which calculates optimal inter-regional "
    "shipments by solving for spatial arbitrage conditions subject to transport arc capacities and freight costs.",
    "**Growth engine driven by Current Annual Increment (CAI)**, where annual roundwood accumulation is interpolated "
    "from yield-age brackets and applied to calculated regional forest areas.",
    "**Integrated carbon accounting system** that evaluates the net balance between process-based manufacturing "
    "emissions, freight-related transport emissions, and long-term carbon storage factors within the harvested wood "
    "product (HWP) pool.",
]:
    bullet(t)
body("The model and related data transformations are encoded in GAMS. It is defined as a Non-Linear Program (NLP) and "
     "solved using high-performance solvers (e.g., CONOPT or SNOPT). Data exploitation and result processing are "
     "handled through GDX-to-CSV translation for integrated reporting of regional revenue, manufacturing tier metrics, "
     "and carbon value chains.").paragraph_format.space_before = Pt(6)

# ---- 2 Existing models ----
heading1("2", "Existing models for wood markets")
body("FORBIOM-ON belongs to the group of recursive-dynamic partial equilibrium models for the forest sector. The "
     "history of these models goes back to the Global Trade Model (GTM), which was the first to study how wood "
     "products move between countries (Buongiorno and Gilless, 1983). Around the same time, the PAPYRUS model was "
     "created to look at the pulp and paper industry in North America (Buongiorno and Gilless, 1987). These early "
     "models created the foundation needed to combine forest growth with market supply and demand.")
body("The most well-known models in this group are the EFI-GTM (Kallio et al., 2004) and the GFPM (Tomberlin and "
     "Buongiorno, 1998). The EFI-GTM is used to study wood markets mostly in Europe. The Global Forest Products Model "
     "(GFPM) is similar but covers the whole world, dividing it into 180 different regions to see how trade flows on a "
     "global scale.")
body("Because global models are too broad to show local policy impacts, researchers have built models for specific "
     "countries and regions. Examples include the Norwegian Trade Model (Tr\u00F8mborg and Sj\u00F8lie, 2011), the "
     "Finnish Forest Sector Model (Ronnila, 1995), and the French Forest Sector Model (Caurla et al., 2010). These "
     "models use high-resolution local data to provide better policy insights for specific jurisdictions.")
body("FORBIOM-ON contributes to this field by providing a comprehensive **vertically integrated framework** for the "
     "Ontario forest sector. While traditional models often treat the forest and the manufacturing sector as separate "
     "units, FORBIOM-ON creates a direct, physical link between the biological growth of specific tree species and the "
     "production limits of advanced wood industries. By accounting for the strict industrial dependencies between "
     "primary sawmilling and secondary manufacturing, the model ensures that the expansion of the mass timber sector "
     "is balanced against the actual sustainable harvest limits of the province. This approach allows for a realistic "
     "evaluation of how regional forest management policies impact the entire value chain. This makes the model a "
     "practical tool for assessing if new wood policies are both environmentally sustainable and industrially feasible.")

# ---- 3 ABM linkage ----
heading1("3", "ABM linkage structure")
body("To align with real-world *behavioral* harvesting, an agent-based module (ABM) can represent harvest decisions "
     "at the level of landowners, contractors, or forest management units (FMUs). Conceptually:")
bullet("**ABM outputs \u2192 optimization inputs:** e.g., effective harvest intensity, adoption of mass timber, or "
       "stochastic perturbations to regional supply and costs, passed as parameters or scenario tables into the GAMS model.")
bullet("**Optimization outputs \u2192 ABM inputs:** shadow values, regional prices, or policy signals that agents use "
       "to update their decision rules.")

ABM_FIG = (os.path.join(HERE, "ABM1.png"), 6.3,
       "Conceptual structure of the agent-based module (ABM) linked to FORBIOM-ON (Ontario forest and wood-sector "
       "spatial optimisation model). Three heterogeneous agent classes operate under bounded rationality (Simon, 1957) "
       "and satisficing behaviour: *Private Landowners* (objective: maximise harvest utility; incomplete price sensing; "
       "risk-averse), *Logging Contractors* (objective: maximise operational profit; equipment/labour constrained; "
       "activated by harvest orders), and *FMU Managers* (objective: enforce sustainability mandates; actions include "
       "setting the allowable annual cut, applying harvest-cap multipliers, and implementing carbon pricing). At each "
       "period *t*, agents sense the market environment and stochastic shocks (yellow) and translate these signals into "
       "harvest decisions via a logistic behavioural harvest rule (orange rectangle). Five output channels (green) pass "
       "agent decisions to the FORBIOM-ON optimisation module (purple rectangle): mass timber adoption rates, stochastic "
       "supply perturbations, cost perturbations, scenario parameter tables, and effective harvest intensity. The "
       "optimiser returns policy signals and shadow values (yellow diamonds, bottom) through a co-evolutionary feedback "
       "loop (pink), informing agent decisions in period *t*\u00A0+\u00A01.")

heading2("Behavioral harvesting (sigmoid)", "3.1")
body("Harvest response to incentives can be summarized by a sigmoid (logistic) mapping from a latent index *z* (e.g., "
     "margin, carbon price, or policy score) to a bounded harvest propensity:")
M = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'


def mr(t):
    return f"<m:r><m:t>{t}</m:t></m:r>"


omml = (f'<m:oMathPara {M}><m:oMath>{mr("σ")}<m:d><m:e>{mr("z")}</m:e></m:d>{mr("=")}'
        f'<m:f><m:num>{mr("1")}</m:num><m:den>{mr("1+")}<m:sSup><m:e>{mr("e")}</m:e><m:sup>{mr("−k")}'
        f'<m:d><m:e>{mr("z−")}<m:sSub><m:e>{mr("z")}</m:e><m:sub>{mr("0")}</m:sub></m:sSub></m:e></m:d>'
        f'</m:sup></m:sSup></m:den></m:f></m:oMath></m:oMathPara>')
p = doc.add_paragraph()
pfmt(p, before=4, after=6, align=WD_ALIGN_PARAGRAPH.CENTER)
p._p.append(parse_xml(omml))
body("with steepness *k* and midpoint *z*~{0}. In implementation, this can appear as (i) a post-processing adjustment "
     "to harvest, (ii) a smoothed cap on harvest rate, or (iii) an ABM decision rule. The implemented agent-based "
     "model (FORBIOM-ABM) uses option (iii): the same logistic form drives contractor supply, mill utilization and "
     "investment decisions. Its specification, data and calibration are documented in Sections 5 and 6.")
figure(*ABM_FIG)

# ---- 4 Methods ----
heading1("4", "Simulation pathways and methods")
body("The base model is a multi-region, multi-product forest value-chain formulation in GAMS: regions *r*, products "
     "*p* (e.g., CLT, glulam, lumber, pulpwood), and years *y*. Roundwood stock evolves with exogenous or shocked "
     "growth; harvest is constrained by sustainability rules and linked to primary processing (lumber, pulpwood) and "
     "downstream mass-timber products. Logistics include inter-regional flows with arc and mill capacity limits. The "
     "economic objective is optimized under a system of feasibility constraints. Specifically, it selects harvest, "
     "production, sales, and inter-regional transport decisions to maximize net value, while simultaneously accounting "
     "for carbon through a policy-relevant carbon cost applied to modeled gross processing and transport emissions.")
heading2("Simulation pathways", "4.1")
for lab, t in [
    ("i", "**Baseline:** fixed exogenous price paths, baseline demand and growth, single solve over the horizon."),
    ("ii", "**Carbon-price sensitivity:** loop over carbon price scenarios; record objective, emissions, net carbon, "
           "revenue, harvest, production, sales."),
    ("iii", "**Mass-timber / demand sensitivity:** scale CLT/glulam demand caps; compare infrastructure-limited vs "
            "demand-driven outcomes."),
    ("iv", "**Policy scenario table:** coded scenarios (e.g., demand steps, lumber price shocks, harvest-cap "
           "multipliers) with regional disaggregation for reporting."),
    ("v", "**Stochastic elements:** region\u2013year shocks to growth, harvest cost, and/or demand caps; use fixed "
          "random seed for reproducibility."),
]:
    enum_item(lab, t)
heading2("Model families and data flow", "4.2")
body("Two complementary models share one data foundation. FORBIOM-ON (GAMS) is a normative spatial optimization: it "
     "finds the value-maximizing allocation of harvest, processing and inter-regional trade under sustainability, "
     "capacity and carbon constraints. FORBIOM-ABM (Python) is a descriptive simulation: it reproduces how "
     "heterogeneous, boundedly rational FMU managers, contractors and processing plants actually respond to prices, "
     "disturbance and policy, and how new technologies are adopted over time. Both models use the same six FMU "
     "regions, harvest cost, lumber-input ratios for mass timber and carbon factors. Figure 2 summarizes the full "
     "data-processing workflow, Section 5 documents each dataset and transformation step, and Section 6 specifies "
     "the agent-based model.")
figure(WORKFLOW, 6.37,
       "Data-processing workflow of the two FORBIOM models. Raw provincial datasets are filtered, harmonized and "
       "aggregated to the six study FMUs by dedicated scripts (`calibrate.py`, `process_fri_data.py`) and by the GAMS "
       "data block, producing model-ready calibration tables and parameters. The dashed gold arrow marks the planned "
       "co-evolutionary coupling between the agent-based simulation and the spatial optimization.")

# --------------------------------------------------------------------------
# Data tables
# --------------------------------------------------------------------------
YEARS = [str(y) for y in range(2020, 2031)]


def data_table(header, rows, widths, merges=(), group_starts=(), light_rules=(), summary_from=None,
               total_rows=(), size=7.5, label_cols=1, header2=None, bold_cols=(0,), group_fill=None,
               row_h=None, left_cols=()):
    """Build a booktabs-style table. rows: list of lists of strings ('' = empty)."""
    n_head = 2 if header2 else 1
    t = doc.add_table(rows=n_head + len(rows), cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(t, top=(14, FOREST), bottom=(14, FOREST))
    vpad = 0 if row_h else 22
    set_table_cell_margins(t, top=vpad, bottom=vpad, left=55, right=55)
    set_col_widths(t, widths)

    def put(cell, text, bold=False, color=INK, align=WD_ALIGN_PARAGRAPH.RIGHT, italic=False, sz=size):
        p = cell.paragraphs[0]
        pfmt(p, before=0, after=0, line=1.0, align=align, keep_next=True)
        if text:
            add_rich(p, text, size=sz, color=color, bold=bold, italic=italic)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    for hi, hdr in enumerate([header] + ([header2] if header2 else [])):
        hr = t.rows[hi]
        mark_header_row(hr)
        cant_split(hr)
        for i, h in enumerate(hdr):
            c = hr.cells[i]
            fill = "7A6A2E" if (summary_from is not None and i >= summary_from) else FOREST
            set_cell_bg(c, fill)
            put(c, h, bold=hi == 0, italic=hi == 1, color="FFFFFF",
                align=WD_ALIGN_PARAGRAPH.LEFT if (i < label_cols or i in left_cols) else WD_ALIGN_PARAGRAPH.CENTER,
                sz=size + (0.5 if hi == 0 else -0.5))

    for ri, vals in enumerate(rows):
        r_ = t.rows[n_head + ri]
        cant_split(r_)
        if row_h:
            r_.height = Inches(row_h)
            r_.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
        is_total = ri in total_rows
        for ci, v in enumerate(vals):
            c = r_.cells[ci]
            if group_fill and group_fill[ri] and ci >= 0:
                set_cell_bg(c, group_fill[ri])
            if summary_from is not None and ci >= summary_from:
                set_cell_bg(c, GOLD_LIGHT)
                if ci == summary_from:
                    set_cell_borders(c, left=(6, GOLD))
            if is_total:
                set_cell_bg(c, SAGE)
                set_cell_borders(c, top=(8, FOREST))
            if ri in group_starts and ri != 0:
                set_cell_borders(c, top=(6, PINE))
            put(c, v, bold=is_total or (ci in bold_cols and ci < label_cols),
                color=FOREST if (ci < label_cols and ci in bold_cols) else INK,
                align=WD_ALIGN_PARAGRAPH.LEFT if (ci < label_cols or ci in left_cols) else WD_ALIGN_PARAGRAPH.RIGHT)
        for (rr, cfrom) in light_rules:
            if rr == ri:
                for ci in range(cfrom, len(vals)):
                    set_cell_borders(r_.cells[ci], top=(3, RULE, "dotted"))

    for i in range(n_head):
        if summary_from is not None:
            set_cell_borders(t.rows[i].cells[summary_from], left=(6, GOLD))
    for (r0, c0, r1, c1) in merges:
        top = t.cell(n_head + r0, c0)
        top.merge(t.cell(n_head + r1, c1))
        top.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    last = t.rows[-1]
    for c in last.cells:
        for p in c.paragraphs:
            p.paragraph_format.keep_with_next = False
    return t


# ==========================================================================
# 5  DATA SOURCES AND DATA PROCESSING
# ==========================================================================
ABM_DIR = os.path.join(HERE, "Archieve", "Rasoul", "SylvaTrend", "ABM_Activity3")


def read_csv(rel):
    with open(os.path.join(ABM_DIR, rel), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


ABM_REG = ["TroutLake", "Abitibi", "Algoma", "Kenora", "Nipissing", "Algonquin"]
NICE = dict(zip(ABM_REG, ["Trout Lake", "Abitibi", "Algoma", "Kenora", "Nipissing", "Algonquin"]))
CAL = {r["region"]: {k: (float(v) if k != "region" else v) for k, v in r.items()} for r in read_csv("calibration/regions.csv")}
CHK = {r["region"]: {k: (float(v) if k != "region" else v) for k, v in r.items()}
       for r in read_csv("results/tables/calibration_check.csv")}
JOBS = read_csv("calibration/efar_jobs.csv")
FLOWS = {r["region"]: {k: (float(v) if k != "region" else v) for k, v in r.items()} for r in read_csv("calibration/efar_fmu_flows.csv")}

COORDS = {"TroutLake": (50.60, -92.30), "Abitibi": (49.30, -81.00), "Algoma": (46.90, -83.90),
          "Kenora": (50.00, -94.30), "Nipissing": (46.60, -79.60), "Algonquin": (45.70, -78.40)}
GTA = (43.70, -79.42)


def road_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h)) * 1.3


DIST = {r: road_km(COORDS[r], GTA) for r in ABM_REG}
k0 = lambda x: f"{x / 1000:,.0f}"
pct = lambda x: f"{100 * x:.0f}%"

heading1("5", "Data sources and data processing").paragraph_format.page_break_before = True
body("This section documents the datasets behind both models, the transformations applied to each, and the resulting "
     "model inputs. All processing is scripted, so every input table can be regenerated from the raw sources "
     "(see Supplementary materials). Table 1 lists the sources; Sections 5.2\u20135.4 describe the processing "
     "chains for FORBIOM-ON, the Forest Resources Inventory and the agent-based model; Section 5.5 lists the known "
     "data gaps.")

heading2("Data sources", "5.1")
caption("Table", "Data sources used by FORBIOM-ON and FORBIOM-ABM.", keep_next=True)
data_table(["Dataset", "Provider and vintage", "Variables used", "Used in"], [
    ["ARWoodS data extract (Annual Report on Wood Supply)", "Ontario MNR, 2025 update; fiscal years 2019\u20132024",
     "Planned available harvest under the Long-Term Management Direction (LTMD) and actual harvest, by management "
     "unit, species group and forest type", "ABM fibre supply and calibration"],
    ["eFAR summary (Electronic Forest industry Annual Report)", "Ontario MNR, September 2024 release; 2020\u20132022",
     "Facility and woodlands employees; roundwood consumed (Section C1); deliveries from source FMUs to facility "
     "types (Sections A and B)", "ABM employment intensities and wood flows"],
    ["Forest Resources Inventory (FRI), FIM v2 geodatabases", "MNR; Abitibi River 2011, Algonquin Park 2011, "
     "Algoma 2013, Trout Lake 2013, Kenora 2015, Nipissing (3D inventory)",
     "Polygon type, species composition, age, height, stocking, crown closure, geometry",
     "Spatial composition and maps (CRIBE ArcGIS dataset)"],
    ["Plonski normal yield tables (metric)", "Ontario yield tables, archived edition",
     "Gross merchantable volume (m^{3}/ha) by age for white pine, jack pine and tolerant hardwoods, site class 1",
     "FORBIOM-ON forest area and growth (CAI)"],
    ["Regional roundwood stocks", "Ontario GeoHub", "Initial standing roundwood stock by FMU", "FORBIOM-ON initial state"],
    ["Market, cost and technology data", "Literature, industry benchmarks, model assumptions",
     "Product prices, processing and harvest costs, demand caps, transport costs, capacities, carbon factors",
     "Both models"],
], [1.45, 1.4, 2.4, 1.12], label_cols=1, left_cols=(1, 2, 3), size=8)
doc.add_paragraph().paragraph_format.space_after = Pt(2)

# ---- 5.2 FORBIOM-ON ----
heading2("FORBIOM-ON input processing (GAMS data block)", "5.2")
heading3("Yield curves")
body("Plonski site-class-1 volumes are entered for three reference species at 10-year ages from 30 to 80 years "
     "(Table 2). The remaining combinations are derived by proxy rules inside the GAMS data block: site class 2 = "
     "0.80 \u00D7 site class 1 and site class 3 = 0.60 \u00D7 site class 1; red pine = white pine; spruce = jack pine; "
     "aspen = 0.90 \u00D7 jack pine; and white birch = 0.80 \u00D7 jack pine.")
caption("Table", "Plonski gross merchantable volume used as site-class-1 reference curves (m^{3}/ha).", keep_next=True)
data_table(["Species", "Age 30", "Age 40", "Age 50", "Age 60", "Age 70", "Age 80"], [
    ["White pine", "76", "157", "242", "315", "372", "414"],
    ["Jack pine", "89", "155", "196", "223", "238", "243"],
    ["Tolerant hardwoods", "36", "68", "100", "130", "158", "185"],
], [1.6] + [0.7] * 6, size=9, group_fill=[None, MIST, None])
doc.add_paragraph().paragraph_format.space_after = Pt(2)

heading3("Regional composition, inferred area and growth")
body("Each FMU is described by a species mix \u03C0~{r,t} (Table 3), a dominant site class *s*~{r}, a representative "
     "initial age *a*^{0}~{r} = 30 years and an initial roundwood stock *S*^{0}~{r} (Table 4). Because the forest area "
     "of each FMU is not entered directly, it is inferred so that the composition-weighted yield at the initial age "
     "reproduces the observed stock:")
equation(msub(mt("A"), mt("r")) + mt("=") +
         mfrac(msubsup(mt("S"), mt("r"), mt("0")) + mt("×") + msup(mt("10", True), mt("6", True)),
               msum(mt("t"), msub(mt("π"), mt("r,t")) + mt("·") +
                    msub(mt("Y"), mt("t,") + msub(mt("s"), mt("r"))) + mpar(msubsup(mt("a"), mt("r"), mt("0"))))))
body("Annual growth is the current annual increment over the next ten-year age bracket, scaled by the inferred area "
     "and multiplied by a region- and year-specific growth shock:")
equation(msub(mt("CAI", True), mt("r")) + mt("=") + mfrac(msub(mt("A"), mt("r")), msup(mt("10", True), mt("6", True)))
         + msum(mt("t"), msub(mt("π"), mt("r,t")) + mt("·") + mfrac(
             msub(mt("Y"), mt("t,") + msub(mt("s"), mt("r"))) + mpar(msubsup(mt("a"), mt("r"), mt("0")) + mt("+10"))
             + mt("−") + msub(mt("Y"), mt("t,") + msub(mt("s"), mt("r"))) + mpar(msubsup(mt("a"), mt("r"), mt("0"))),
             mt("10", True))))
equation(msub(mt("G"), mt("r,y")) + mt("=") + msub(mt("CAI", True), mt("r")) + mt("·") +
         msubsup(mt("ε"), mt("r,y"), mt("G")) + mt(",    ") + msubsup(mt("ε"), mt("r,y"), mt("G")) + mt("=0.88+0.24·") +
         mfrac(mt("mod", True) + mpar(mt("31") + mt("r") + mt("+17") + mt("y") + mt("+7,  97")), mt("97", True)))
body("The growth multiplier ranges from 0.88 to 1.12 (\u00B112%). It is generated by a deterministic hash rather than a "
     "random draw, so growth paths are identical across runs and scenarios. Standing stock then evolves recursively as "
     "stock plus growth minus harvest, and annual harvest is capped at 1% of standing stock in each FMU.")

SPECIES_MIX = [
    ("Trout Lake", [50, 30, 10, 0, 0, 0, 10]), ("Abitibi", [60, 20, 10, 0, 0, 0, 10]),
    ("Algoma", [10, 5, 10, 40, 30, 5, 0]), ("Kenora", [40, 40, 10, 0, 0, 5, 5]),
    ("Nipissing", [10, 5, 10, 30, 40, 5, 0]), ("Algonquin", [5, 0, 10, 50, 30, 5, 0]),
]
caption("Table", "Species composition by FMU used in FORBIOM-ON (% of stock).", keep_next=True)
data_table(["Region", "Spruce", "Jack pine", "White birch", "Tol. hardwoods", "White pine", "Red pine", "Aspen"],
           [[r] + [str(v) for v in vals] for r, vals in SPECIES_MIX],
           [1.15] + [0.74] * 7, size=8.5, group_fill=[None, MIST] * 3)
doc.add_paragraph().paragraph_format.space_after = Pt(2)

REG_IN = [
    ("Trout Lake", "28,999.48", "SC2", "3.5", "3.0"), ("Abitibi", "107,775.22", "SC2", "5.0", "6.0"),
    ("Algoma", "54,884.89", "SC1", "4.5", "5.0"), ("Kenora", "49,746.19", "SC3", "2.5", "2.0"),
    ("Nipissing", "45,261.69", "SC1", "6.5", "7.0"), ("Algonquin", "36,725.26", "SC1", "4.0", "4.0"),
]
caption("Table", "Regional inputs to FORBIOM-ON: initial stock, dominant site class and base final-demand caps "
                 "(million m^{3}/yr).", keep_next=True)
data_table(["Region", "Initial stock\u2020", "Site class", "Lumber", "Pulpwood", "CLT", "Glulam"],
           [[a, b, c, d, e, "0.17", "0.17"] for a, b, c, d, e in REG_IN],
           [1.15, 1.2, 0.8, 0.8, 0.8, 0.8, 0.8], size=8.5, left_cols=(2,), group_fill=[None, MIST] * 3)
notes(["\u2020 Values as entered in the GAMS data block (`initialStockRegion`), where they are labelled million m^{3}. "
       "Their magnitude suggests thousand m^{3}; the unit should be verified before final publication.",
       "Demand caps are multiplied each year by (1 + *g*)^{t} with *g* = 0 in the baseline and by a stochastic "
       "multiplier drawn from U(0.88, 1.12) for each region, product and year."])

heading3("Prices, processing costs and product chain")
body("Product prices follow exogenous paths that grow by 3% per year from their 2020 base, while unit processing costs "
     "decline by 2% per year to represent efficiency gains. Processing cost is the sum of a layer-specific base cost "
     "($100/m^{3} primary, $50/m^{3} secondary) and a product mark-up. Secondary products are tied to primary output "
     "through the lumber-input ratio, which enforces the mass balance between sawmilling and mass-timber manufacturing. "
     "Roundwood harvest costs $38/m^{3}, multiplied by a region\u2013year shock drawn from U(0.90, 1.10).")
equation(msub(mt("P"), mt("p,y")) + mt("=") + msub(mt("P"), mt("p,2020")) + mt("·") +
         msup(mt("1.03", True), mt("y−2020")) + mt(",      ") + msub(mt("c"), mt("p,y")) + mt("=") +
         msub(mt("c"), mt("p,2020")) + mt("·") + msup(mt("0.98", True), mt("y−2020")))
caption("Table", "Product parameters in FORBIOM-ON (2020 values).", keep_next=True)
data_table(["Product", "Tier", "Price ($/m^{3})", "Processing cost ($/m^{3})", "Yield factor",
            "Lumber input (m^{3}/m^{3})", "Process emissions (tCO~{2}/m^{3})", "Carbon storage (tCO~{2}/m^{3})"], [
    ["CLT", "Secondary", "700", "200", "0.82", "1.20", "0.150", "0.70"],
    ["Glulam", "Secondary", "575", "170", "0.85", "1.10", "0.170", "0.70"],
    ["Lumber", "Primary", "375", "120", "0.90", "\u2014", "0.065", "0.40"],
    ["Pulpwood", "Primary", "75", "20", "0.98", "\u2014", "0.010", "0.07"],
], [0.75, 0.75, 0.65, 0.85, 0.6, 0.85, 0.96, 0.96], size=8, left_cols=(1,), group_fill=[None, MIST] * 2)
doc.add_paragraph().paragraph_format.space_after = Pt(2)

heading3("Logistics, capacities and carbon")
body("Inter-regional shipments use the transport cost matrix in Table 6 for every product. Arc capacities (20 million "
     "m^{3}/yr per arc and product) and mill capacities (10 million m^{3}/yr for lumber and pulpwood; 1.0 million "
     "m^{3}/yr for CLT and glulam) are placeholders that will be replaced with observed mill and road capacities. "
     "Freight emissions are 0.018 tCO~{2}/m^{3} shipped. The carbon price multiplies process and freight "
     "emissions in the objective; carbon stored in products is reported separately as the harvested-wood-product pool.")
TRANS = [
    ("Trout Lake", "0", "38", "42", "100", "14", "9"), ("Abitibi", "26", "0", "35", "75", "25", "32"),
    ("Algoma", "31", "28", "0", "60", "31", "38"), ("Kenora", "79", "61", "49", "0", "79", "87"),
    ("Nipissing", "14", "27", "31", "79", "0", "8"), ("Algonquin", "9", "34", "38", "87", "8", "0"),
]
caption("Table", "Transport cost proxy between FMUs ($/m^{3}; rows = origin, columns = destination).", keep_next=True)
data_table(["Origin \\ destination", "Trout Lake", "Abitibi", "Algoma", "Kenora", "Nipissing", "Algonquin"],
           [list(r) for r in TRANS], [1.45] + [0.8] * 6, size=8.5, group_fill=[None, MIST] * 3)
doc.add_paragraph().paragraph_format.space_after = Pt(2)

heading3("Output processing")
body("Solutions are stored in GDX files and exported to CSV (GDX-to-CSV) by region, product, year and manufacturing "
     "tier. Post-processing aggregates them into production, revenue and processing cost by tier (Table 16), "
     "regional revenue, and gross emissions, stored carbon and net carbon for each carbon-price and demand scenario. "
     "R and Python scripts then produce the tables and figures in Section 7.")

# ---- 5.3 FRI ----
heading2("Forest Resources Inventory processing (process_fri_data.py)", "5.3")
body("The FRI geodatabases provide polygon-level forest descriptions for the six FMUs. They are processed with a "
     "Python pipeline (GeoPandas, pyogrio, Shapely) in seven steps:")
for lab, t in [
    ("1", "Extract the six FIM v2 archives and locate the forest polygon layer; for Trout Lake, all polygon layers are "
          "read and concatenated."),
    ("2", "Read large layers in 20,000-row chunks (Nipissing holds about 130,000 polygons) and strip Z/M "
          "coordinates from the 3D inventory."),
    ("3", "Harmonize attribute names across inventory vintages (`OSPCOMP` \u2192 `SPCOMP`, `OAGE` \u2192 `AGE`, "
          "`OHT` \u2192 `HT`) into one schema."),
    ("4", "Reproject to Statistics Canada Lambert (EPSG:3347) in 4,000-row slices and compute planar polygon area "
          "(m^{2} and ha)."),
    ("5", "Keep forested polygons only (`POLYTYPE` = FOR)."),
    ("6", "Compute a provisional volume index, *V* = stocking \u00D7 height \u00D7 crown closure/100 \u00D7 area (ha) "
          "\u00D7 10, and a provisional biomass index of 0.5 \u00D7 *V*."),
    ("7", "Dissolve polygons by FMU, sum area and biomass, and export GeoPackage layers for mapping."),
]:
    enum_item(lab, t)
body("Step 6 uses placeholder coefficients. The FRI outputs therefore serve spatial composition and mapping only; they "
     "are not yet direct model inputs. The planned replacement computes polygon volumes from the yield curves in "
     "Section 5.2 and FRI species composition, and converts them to biomass with species-specific expansion "
     "factors.").paragraph_format.space_before = Pt(4)

# ---- 5.4 ABM calibration ----
heading2("Agent-based model data and calibration (calibrate.py)", "5.4")
heading3("Fibre supply and harvest (ARWoodS)")
body("The ARWoodS extract is filtered to the six management units (Trout Lake Forest, Abitibi River Forest, Algoma "
     "Forest, Kenora Forest, Nipissing Forest and Algonquin Park Forest), to merchantable volume (`FT` = Merch) and to "
     "fiscal years 2019\u20132024. ARWoodS species groups are mapped to three fibre classes: softwood (SW) = "
     "spruce\u2013pine\u2013fir (SPF), white and red pine (PWR), other conifers (OC) and cedar (CE); poplar (PO); and "
     "hardwood (HW) = white birch (BW) and tolerant hardwoods (TOL). Actual harvest and LTMD volumes are summed by FMU "
     "and fibre class and divided by six to give annual means. Utilization is harvest divided by LTMD.")
act_tot = sum(CAL[r]["ACT_total"] for r in ABM_REG)
ltmd_tot = sum(CAL[r]["LTMD_total"] for r in ABM_REG)
rows = []
for r in ABM_REG:
    c, k = CAL[r], CHK[r]
    rows.append([NICE[r], k0(c["LTMD_total"]), k0(c["ACT_total"]), pct(c["utilization"]),
                 k0(c["LTMD_SW"] - c["ACT_SW"]), k0(c["LTMD_PO"] - c["ACT_PO"]), k0(c["LTMD_HW"] - c["ACT_HW"]),
                 k0(k["simulated_2026"]), f"{k['error_pct']:+.1f}%"])
rows.append(["Total", k0(ltmd_tot), k0(act_tot), pct(act_tot / ltmd_tot),
             k0(sum(CAL[r]["LTMD_SW"] - CAL[r]["ACT_SW"] for r in ABM_REG)),
             k0(sum(CAL[r]["LTMD_PO"] - CAL[r]["ACT_PO"] for r in ABM_REG)),
             k0(sum(CAL[r]["LTMD_HW"] - CAL[r]["ACT_HW"] for r in ABM_REG)),
             k0(sum(CHK[r]["simulated_2026"] for r in ABM_REG)), ""])
caption("Table", "Fibre supply, observed harvest and calibration check by FMU (1,000 m^{3}/yr; ARWoodS FY2019\u20132024 "
                 "means; simulated values are the mean of 50 business-as-usual runs).", keep_next=True)
data_table(["FMU", "LTMD", "Harvest", "Utilization", "Unused SW", "Unused PO", "Unused HW", "Simulated 2026", "Error"],
           rows, [1.0, 0.65, 0.65, 0.7, 0.7, 0.7, 0.7, 0.75, 0.52], size=8, total_rows=(6,),
           group_fill=[None, MIST] * 3 + [None])
doc.add_paragraph().paragraph_format.space_after = Pt(2)
body(f"Across the six FMUs, LTMD averages {ltmd_tot / 1e6:.2f} million m^{{3}}/yr against an actual harvest of "
     f"{act_tot / 1e6:.2f} million m^{{3}}/yr, a utilization of {pct(act_tot / ltmd_tot)}. Utilization ranges from "
     f"{pct(CAL['Kenora']['utilization'])} in Kenora to {pct(CAL['TroutLake']['utilization'])} in Trout Lake. Unused "
     "softwood is concentrated in Abitibi, Trout Lake, Kenora and Nipissing; unused poplar and hardwood in Abitibi, "
     "Algoma, Algonquin and Kenora.")

heading3("Employment and wood flows (eFAR)")
body("Three eFAR tables are processed for 2020\u20132022 and averaged over the three years. Facility and woodlands "
     "employees come from the Facility Info section; roundwood consumed by facility type comes from Section C1. "
     "Dividing employees by consumption gives direct jobs per 1,000 m^{3} (Table 8). Deliveries in Sections A and B "
     "are matched to the six FMUs by source name to give wood flows from each FMU to each facility type (Table 9). "
     "The ABM uses the sawmill intensity (0.36 facility + 0.05 woodlands jobs per 1,000 m^{3}) for softwood mills and "
     "the composite intensity (0.36 + 0.01) for poplar mills.")
JOB_ORDER = ["Sawmill", "Composite", "Pulp", "Veneer", "Bioproduct", "Fuelwood"]
jrows = []
for name in JOB_ORDER:
    j = next(x for x in JOBS if x["FacilityTypeName"] == name)
    jrows.append([name, f"{float(j['FacilityEmployees']):,.0f}", f"{float(j['WoodlandsEmployees']):,.0f}",
                  f"{float(j['roundwood_m3']) / 1000:,.0f}", f"{float(j['facility_jobs_per_1000m3']):.2f}",
                  f"{float(j['woodlands_jobs_per_1000m3']):.2f}"])
caption("Table", "Employment intensity by facility type, Ontario, eFAR 2020\u20132022 annual means.", keep_next=True)
data_table(["Facility type", "Facility employees", "Woodlands employees", "Roundwood consumed (1,000 m^{3})",
            "Facility jobs per 1,000 m^{3}", "Woodlands jobs per 1,000 m^{3}"],
           jrows, [1.2, 0.95, 0.95, 1.1, 1.05, 1.1], size=8.5, group_fill=[None, MIST] * 3)
doc.add_paragraph().paragraph_format.space_after = Pt(2)
FL_COLS = ["Sawmill", "Composite", "Pulp", "Veneer", "Other"]
caption("Table", "Roundwood delivered from the six FMUs by facility type (1,000 m^{3}/yr, eFAR 2020\u20132022 means).",
        keep_next=True)
data_table(["FMU"] + FL_COLS + ["Total"],
           [[NICE[r]] + [f"{FLOWS[r][c] / 1000:,.1f}" for c in FL_COLS] + [f"{sum(FLOWS[r][c] for c in FL_COLS) / 1000:,.1f}"]
            for r in ABM_REG], [1.2, 0.85, 0.85, 0.85, 0.85, 0.85, 0.85], size=8.5, group_fill=[None, MIST] * 3)
doc.add_paragraph().paragraph_format.space_after = Pt(2)

heading3("Agent initialization")
body("Agents are initialized from the calibration tables so that the first simulated year reproduces observed "
     "conditions:")
bullet("**Harvest contractors:** ten per FMU. Total contractor capacity is 1.25 \u00D7 the observed harvest, split "
       "among contractors with Dirichlet(3) weights. Individual cost multipliers are drawn from a lognormal(0, 0.08) "
       "distribution. The initial share of Indigenous-owned contractors is 20% (Trout Lake), 15% (Abitibi), 35% "
       "(Kenora) and 10% elsewhere.")
bullet("**Incumbent mills:** three per FMU and fibre class wherever observed harvest exceeds 1,000 m^{3}/yr (51 mills; "
       "Kenora has no hardwood mill). They hold 50%, 30% and 20% of the class volume, with cost multipliers drawn from "
       "lognormal(0, 0.05). Each mill's capacity is back-solved so that its year-0 desired intake equals its share of "
       "observed harvest:")
equation(msub(mt("Cap", True), mt("j")) + mt("=") + mfrac(
    msub(mt("s"), mt("j")) + mt("·") + msubsup(mt("H"), mt("r,f"), mt("obs", True)),
    mt("σ") + mpar(mt("4·") + mfrac(msub(mt("v"), mt("j,f")) + mt("−") + msub(mt("w"), mt("r,f,0")),
                                     msub(mt("w"), mt("r,f,0"))) + mt("+1"))))
bullet("**Log prices:** the initial regional log price is 1.10 \u00D7 the delivered contractor cost, which combines "
       "harvest cost ($38/m^{3} \u00D7 regional access factor 1.00\u20131.15, +10% for poplar and hardwood), 110 km "
       "of in-region haul at $0.12/m^{3}\u00B7km and $6/m^{3} stumpage.")
bullet("**Distances:** road distances are approximated from FMU centroids as great-circle distance \u00D7 1.3 "
       "circuity. Distances to the Greater Toronto Area (GTA) market are "
       + ", ".join(f"{NICE[r]} {DIST[r]:,.0f} km" for r in ABM_REG) + ".")

heading3("Calibration check and validation")
body("The simulated 2026 harvest matches the observed 2019\u20132024 mean exactly in Abitibi, Algoma, Nipissing and "
     f"Algonquin, and is within {abs(CHK['TroutLake']['error_pct']):.2f}% in Trout Lake and "
     f"{abs(CHK['Kenora']['error_pct']):.1f}% in Kenora (Table 7). As a pattern-oriented validation, the 50 "
     "business-as-usual runs keep province-wide utilization well below LTMD: the 2041\u20132045 mean is 41% "
     "(standard deviation 8.6 percentage points), compared with 46% observed in 2019\u20132024. The spread reflects "
     "lumber-price cycles and occasional mill exits. Behavioural parameters (logistic slopes and adjustment speeds) "
     "were set to give plausible responses and tested in the sensitivity analysis (Section 6.7).")

heading2("Data quality and known gaps", "5.5")
for t in [
    "**Placeholder logistics data:** arc capacities, mill capacities and the transport cost matrix in FORBIOM-ON are "
    "proxies awaiting observed mill-capacity and road-network data.",
    "**Yield proxies:** only three species are entered from Plonski at site class 1; other species and site classes "
    "are derived by fixed ratios, so growth differences between FMUs are driven mainly by species mix and site class.",
    "**Stock units:** the initial stock values should be checked against the GeoHub source (see Table 4 note).",
    "**FRI biomass index:** the volume and biomass coefficients in the FRI pipeline are placeholders (Section 5.3).",
    "**Community parameters in the ABM:** northern housing need, community heat demand and fuel costs, and Indigenous "
    "labour and contractor shares are planning assumptions that need validation with communities and MNR.",
    "**Time frames:** FORBIOM-ON runs 2020\u20132030, while the ABM is calibrated to 2019\u20132024 data and simulates "
    "2026\u20132045. Coupling the two models will require a common horizon.",
]:
    bullet(t)

# ==========================================================================
# 6  AGENT-BASED MODEL
# ==========================================================================
heading1("6", "Agent-based model (FORBIOM-ABM): specification and experiments")
body("FORBIOM-ABM simulates how forest biomass is harvested, processed and used in the six study FMUs when "
     "heterogeneous, boundedly rational agents respond to prices, disturbance and policy. It is described here "
     "following the ODD protocol (Overview, Design concepts and Details; Grimm et al., 2020). The model is "
     "implemented in Python 3.11 (NumPy, pandas) in `abm.py`; experiments are run by `experiments.py`.")

heading2("Purpose and patterns", "6.1")
body("The model evaluates how alternative combinations of processing technologies and policies change biomass "
     "utilization, regional economic activity, Indigenous and rural benefits, carbon outcomes and investment risk. "
     "It is designed to reproduce three observed patterns: (i) FMU-level harvest well below LTMD, with large "
     "differences between regions; (ii) persistent under-utilization of poplar and hardwood relative to softwood; and "
     "(iii) the sensitivity of harvest to lumber prices, including mill curtailment and closure after sustained losses.")

heading2("Entities, state variables and scales", "6.2")
caption("Table", "Agents and entities in FORBIOM-ABM.", keep_next=True)
data_table(["Agent / entity", "Key state variables", "Behaviour"], [
    ["FMU manager (6)", "LTMD by fibre class (SW, PO, HW); available volume after disturbance",
     "Releases sustainable volume; allocates fibre to licence holders, then entrants (Indigenous-majority entrants "
     "first under the priority policy)"],
    ["Harvest contractor (10 per FMU at start)", "Capacity (m^{3}/yr), cost multiplier, Indigenous ownership, sales, margin",
     "Offers volume through a logistic response to the log price relative to own cost; expands when fully used and "
     "profitable"],
    ["Incumbent mill (51)", "Calibrated capacity, fibre class, cost multiplier, consecutive loss years",
     "Sets utilization from expected margin; exits after three loss years with probability 0.4 per year"],
    ["Mass-timber hub (entrant)", "150,000 m^{3}/yr log intake; 60,000 m^{3}/yr CLT/glulam; capex $150 M; Indigenous equity",
     "Integrated sawmill and CLT/glulam line selling to southern Ontario; surplus lumber to commodity markets"],
    ["Urban CLT plant (entrant, GTA)", "60,000 m^{3}/yr; capex $100 M", "Converts lumber bought from the north; adds no harvest"],
    ["Community log-to-panel spoke (entrant)", "25,000 m^{3}/yr logs; 10,000 m^{3}/yr panels; capex $25 M; Indigenous equity",
     "Small sawmill and prefab panel line; serves northern housing first, then southern prefab demand"],
    ["Community bioheat (entrant)", "5,000 odt/yr; capex $12 M", "Displaces heating oil; uses residues first, then low-grade roundwood"],
    ["Pellet plant (entrant)", "80,000 odt/yr; capex $50 M", "Exports pellets by rail via Thunder Bay or Montreal"],
    ["Markets", "AR(1) price shocks; demand levels", "Southern mass timber and panels clear on price; northern housing; heat; commodities"],
    ["Policy agent", "Grants, equity rules, allocation priority, capacity building, procurement, clean-heat incentive",
     "Defined by the strategy (Section 6.6)"],
], [1.55, 2.2, 2.62], label_cols=1, left_cols=(1, 2), size=7.5, group_fill=[None, MIST] * 5)
doc.add_paragraph().paragraph_format.space_after = Pt(2)
body("Spatial scale: six FMU regions plus a GTA market and processing node. Temporal scale: annual steps from 2026 to "
     "2045. Monetary values are 2026 Canadian dollars (real). The implementation operationalizes two of the three "
     "agent classes in Figure 1, FMU managers and logging contractors, and adds processing-plant agents. Private "
     "landowners are not yet represented because the six study FMUs are managed Crown forests.")

heading2("Process overview and scheduling", "6.3")
body("Each annual step runs in the following order:")
for lab, t in [
    ("1", "**Environment:** draw correlated price shocks (lumber, OSB, mass timber, panels, pellets, heating fuel) and "
          "FMU disturbance (fire or blowdown)."),
    ("2", "**Supply release:** FMU managers release available volume by fibre class."),
    ("3", "**Processor demand:** plants form desired roundwood intake from expected margins (logistic utilization rule)."),
    ("4", "**Fibre markets:** contractors offer volume (logistic supply rule); each regional market allocates volume "
          "by priority group and updates the log price in proportion to excess demand."),
    ("5", "**Production and product markets:** southern mass-timber and panel prices clear against demand; spokes "
          "serve local housing first; bioenergy plants use mill surplus residues, then forest residues, then "
          "low-grade roundwood."),
    ("6", "**Accounting:** profits after capital charges, jobs, Indigenous jobs and income, carbon and public cost."),
    ("7", "**Investment:** potential entrants evaluate NPV under adaptive expectations, fibre and market headroom, "
          "learning-adjusted capex and grants; they build with a logistic probability, come online after two years "
          "and ramp up through 50% and 80% of capacity."),
    ("8", "**Exit and adaptation:** loss-making plants may exit, contractors expand capacity, and all agents update "
          "price expectations."),
]:
    enum_item(lab, t)

heading2("Behavioural decision rules", "6.4")
body("All firm decisions use the logistic rule from Section 3.1, applied to a relative margin. Agents are boundedly "
     "rational (Simon, 1957): rather than optimizing, they respond smoothly to expected margins, and the steepness "
     "*k* controls how close the response is to a switch.")
heading3("Contractor supply")
body("Contractor *i* offers volume of fibre class *f* according to its capacity *K*~{i}, the share of effort *e*~{f} "
     "allocated to that fibre (proportional to buyers' demand), the regional log price *w*~{r,f} and its own "
     "delivered cost *c*~{i,r,f}:")
equation(msub(mt("q"), mt("i,f")) + mt("=") + msub(mt("K"), mt("i")) + mt("·") + msub(mt("e"), mt("f")) + mt("·σ") +
         mpar(mt("12·") + mfrac(msub(mt("w"), mt("r,f")) + mt("−") + msub(mt("c"), mt("i,r,f")),
                                msub(mt("c"), mt("i,r,f"))) + mt("+1")))
heading3("Mill utilization")
body("Plant *j* demands roundwood according to its willingness to pay *v*~{j,f}, the net product value per m^{3} of "
     "logs after conversion cost, product freight and residue value, relative to the expected log price:")
equation(msub(mt("D"), mt("j,f")) + mt("=") + msub(mt("Cap", True), mt("j")) + mt("·σ") +
         mpar(mt("4·") + mfrac(msub(mt("v"), mt("j,f")) + mt("−E") + mpar(msub(mt("w"), mt("r,f")), "[", "]"),
                               mt("E") + mpar(msub(mt("w"), mt("r,f")), "[", "]")) + mt("+1")))
heading3("Investment")
body("A candidate plant estimates its expected annual margin at 90% of capacity, after checking fibre headroom "
     "(uncommitted softwood of at least 70% of log capacity for hubs and spokes) and market headroom (at least 40% of "
     "plant capacity for mass-timber plants). It builds with probability:")
equation(mt("Pr", True) + mpar(mt("build", True)) + mt("=0.6·σ") +
         mpar(mt("5·") + mfrac(mt("NPV", True), msup(mt("I"), mt("net", True))) + mt("−1")) + mt(",    ") +
         mt("NPV", True) + mt("=") + mover_bar("m") + mt("·") + mt("AF", True) + mpar(mt("8%, 20 yr", True)) +
         mt("−") + msup(mt("I"), mt("net", True)))
body("Here *I*^{net} is capex net of grants after learning-by-doing (10% reduction per doubling of plants built), and "
     "AF is the annuity factor at an 8% private discount rate over 20 years. Each region can host at most two hubs, "
     "three spokes, four bioheat plants and one pellet plant; the GTA can host three urban CLT plants.")
caption("Table", "Parameterization of the logistic decision rules, \u03C3(*z*) = 1/(1 + e^{\u2212k(z\u2212z0)}).",
        keep_next=True)
data_table(["Decision", "Latent index z", "Steepness k", "Midpoint z0", "Output"], [
    ["Contractor supply", "(log price \u2212 own cost)/own cost", "12", "\u22120.083", "Share of capacity offered"],
    ["Mill utilization", "(willingness to pay \u2212 expected log price)/expected log price", "4", "\u22120.25",
     "Share of capacity demanded"],
    ["Urban CLT output", "Expected margin over lumber cost", "4", "\u22120.25", "Share of capacity produced"],
    ["Investment", "NPV/net capex", "5", "0.20", "Build probability (scaled by 0.6)"],
], [1.25, 2.3, 0.8, 0.8, 1.22], label_cols=1, left_cols=(1, 4), size=8, group_fill=[None, MIST] * 2)
notes(["Negative midpoints mean that agents still operate at about half capacity when margins are slightly negative "
       "in the short run, which reflects contractual commitments and fixed-cost recovery."])

heading2("Markets, expectations and stochasticity", "6.5")
body("**Log prices.** Each regional fibre market clears at min(demand, offered supply, released LTMD). Licence "
     "holders are served before entrants; under the Indigenous-priority policy, Indigenous-majority entrants and "
     "Indigenous contractors are served first. The log price then moves toward market balance, bounded below by 90% "
     "of the lowest contractor cost and above by the highest willingness to pay:")
equation(msub(mt("w"), mt("r,f,t+1")) + mt("=") + msub(mt("w"), mt("r,f,t")) + mt("·") +
         mpar(mt("1+0.3·") + mt("clip", True) + mpar(mfrac(mt("D−S"), mt("S")) + mt(", −0.5, 0.5"))))
body("**Expectations.** Agents update price expectations adaptively with weight 0.3:")
equation(msub(mt("E"), mt("t+1")) + mpar(mt("P"), "[", "]") + mt("=") + msub(mt("E"), mt("t")) +
         mpar(mt("P"), "[", "]") + mt("+0.3") + mpar(msub(mt("P"), mt("t")) + mt("−") + msub(mt("E"), mt("t")) +
                                                      mpar(mt("P"), "[", "]")))
body("**Product prices.** Reference prices are perturbed by autoregressive log-shocks, correlated with the lumber "
     "shock *z*~{L,t}:")
equation(msub(mt("x"), mt("k,t")) + mt("=0.6·") + msub(mt("x"), mt("k,t−1")) + mt("+") +
         msqrt(mt("1−") + msup(mt("0.6", True), mt("2", True))) + mt("·") + msub(mt("σ"), mt("k")) + mt("·") +
         mpar(msub(mt("ρ"), mt("k")) + msub(mt("z"), mt("L,t")) + mt("+") +
              msqrt(mt("1−") + msubsup(mt("ρ"), mt("k"), mt("2", True))) + msub(mt("ε"), mt("k,t"))) +
         mt(",    ") + msub(mt("P"), mt("k,t")) + mt("=") + msub(mover_bar("P"), mt("k")) + mt("·") +
         msup(mt("e", True), msub(mt("x"), mt("k,t"))))
body("The southern mass-timber price then clears against demand with an elasticity of 1.5: when supply exceeds "
     "demand, the price falls to P^{ref}\u00B7(D/S)^{1/1.5}. Table 12 lists all stochastic elements in both models.")
caption("Table", "Stochastic elements in FORBIOM-ABM and FORBIOM-ON.", keep_next=True)
data_table(["Model", "Element", "Specification"], [
    ["ABM", "Product prices", "AR(1) log-shocks, \u03C1 = 0.6; standard deviation 15% (lumber, OSB), 10% (pellets, "
                              "heating fuel), 6% (mass timber), 5% (panels); correlation with the lumber shock 0.6 "
                              "(OSB), 0.4 (mass timber), 0.3 (panels)"],
    ["ABM", "Natural disturbance", "Fire or blowdown with probability 6% per FMU-year; volume loss U(10%, 30%) of LTMD"],
    ["ABM", "Supply noise", "Multiplicative N(1, 0.05) on released volume"],
    ["ABM", "Agent heterogeneity", "Contractor capacity shares Dirichlet(3); cost multipliers lognormal(0, 0.08) for "
                                   "contractors and lognormal(0, 0.05) for mills"],
    ["ABM", "Discrete decisions", "Investment, exit and contractor expansion use decision-keyed uniform draws, so the "
                                  "same decision faces the same random number in every strategy (common random numbers)"],
    ["FORBIOM-ON", "Growth", "Multiplier in [0.88, 1.12] from a deterministic hash of region and year"],
    ["FORBIOM-ON", "Harvest cost", "Multiplier U(0.90, 1.10) by region and year"],
    ["FORBIOM-ON", "Demand caps", "Multiplier U(0.88, 1.12) by region, product and year; fixed seed for reproducibility"],
], [1.0, 1.35, 4.02], label_cols=1, left_cols=(1, 2), size=8, group_fill=[None] * 5 + [MIST] * 3)
doc.add_paragraph().paragraph_format.space_after = Pt(2)

heading2("Biomass utilization strategies", "6.6")
caption("Table", "Strategies simulated in FORBIOM-ABM.", keep_next=True)
data_table(["Code", "Strategy", "Technologies and policies"], [
    ["S0", "Business as usual", "Incumbent mills only; no new technologies or policies"],
    ["S1", "Southern urban mass-timber plants", "Up to three 60,000 m^{3}/yr CLT/glulam plants in the GTA buying "
                                               "northern lumber; no grants"],
    ["S2", "Northern integrated log-to-mass-timber hubs", "Hubs in all six FMUs; 15% capital grant; 20% Indigenous equity"],
    ["S3", "Distributed Indigenous/community network", "Log-to-panel spokes and community bioheat in all FMUs; grants "
                                                      "40% (spokes) and 50% (bioheat); 51% Indigenous equity; "
                                                      "contractor capacity building"],
    ["S4", "Hub-and-spoke hybrid", "Hubs, spokes, bioheat and pellet plants; grants 15/40/50/10%; Indigenous equity "
                                  "20/51/51/20%"],
    ["S5", "Hybrid + enabling policy", "S4 plus capacity building, Indigenous allocation priority, 25% public "
                                       "procurement uplift to southern demand and a $50/tCO~{2}e clean-heat incentive"],
    ["S6", "Regionally differentiated portfolio", "S5 tuned region by region: the pellet plant is dropped in Algoma, "
                                                  "Kenora, Nipissing and Algonquin; the full package is kept in Trout "
                                                  "Lake and Abitibi"],
], [0.5, 1.9, 3.97], label_cols=1, left_cols=(1, 2), size=8, group_fill=[None, MIST] * 3 + [None])
notes(["Capacity building adds Indigenous contractor capacity equal to 2% of LTMD per FMU per year during the first "
       "five years, at a public cost of $20 per m^{3} of capacity, and raises Indigenous contractors' expansion "
       "probability by 60%."])

heading2("Experimental design and multi-criteria evaluation", "6.7")
body("Experiments run in three stages. Strategies are compared with common random numbers, so differences between "
     "strategies are not confounded by different random draws.")
for lab, t in [
    ("1", "**Strategy comparison:** S0\u2013S5 under three southern mass-timber demand growth scenarios (Low 3%, "
          "Base 8%, High 15% per year), with 50 seeds each."),
    ("2", "**Regional tuning:** for each FMU, variants of S5 that drop one technology or cap spokes at one are tested "
          "with 30 seeds (930 runs). A variant is adopted when it improves the weighted regional and provincial "
          "score without lowering the provincial score and reduces public cost. The result is S6, which is then run "
          "under the three demand scenarios with 50 seeds."),
    ("3", "**Sensitivity analysis:** all seven strategies under six one-at-a-time changes (mass-timber price "
          "\u00B120%, lumber price \u221220%, capex +30%, private discount rate 10%, heat value \u221230%), with 30 "
          "seeds each."),
]:
    enum_item(lab, t)
body("In total, stages 1 and 3 comprise 2,310 simulations (7 strategies \u00D7 3 demand scenarios \u00D7 50 seeds, "
     "plus 6 sensitivity cases \u00D7 7 strategies \u00D7 30 seeds), in addition to the 930 tuning runs. Each run is "
     "summarized into seven criteria. Each criterion is min\u2013max normalized across strategies (reversed for "
     "criteria to be minimized) and combined with four weighting schemes (Table 14). Ranking robustness is assessed "
     "across the three demand scenarios and six sensitivity cases. NPVs use a 4% social discount rate.")
caption("Table", "Evaluation criteria and weighting schemes.", keep_next=True)
data_table(["Criterion", "Indicator", "Direction", "Equal", "Economic", "Community", "Climate"], [
    ["Fibre utilization", "Harvest/LTMD, 2041\u20132045", "+", "0.14", "0.20", "0.10", "0.20"],
    ["Value added", "NPV of profits, contractor margins and wages", "+", "0.14", "0.35", "0.10", "0.15"],
    ["Rural/northern jobs", "Mean FTE 2036\u20132045, excluding the GTA", "+", "0.14", "0.10", "0.25", "0.10"],
    ["Indigenous community income", "NPV of wages, contractor margins and equity income", "+", "0.14", "0.10", "0.35", "0.10"],
    ["Net carbon benefit", "Cumulative storage + avoided emissions \u2212 emissions", "+", "0.14", "0.10", "0.10", "0.35"],
    ["Public cost", "Cumulative grants and programme costs", "\u2212", "0.14", "0.10", "0.05", "0.05"],
    ["Investment risk", "Share of new plants with negative cumulative profit", "\u2212", "0.14", "0.05", "0.05", "0.05"],
], [1.45, 2.2, 0.62, 0.5, 0.55, 0.55, 0.5], label_cols=1, left_cols=(1,), size=8, group_fill=[None, MIST] * 3 + [None])
notes(["Equal weights are 1/7 for each criterion.",
       "Score for strategy *s*: \u03A3~{c} w~{c} \u00B7 (x~{s,c} \u2212 min~{s} x~{c})/(max~{s} x~{c} \u2212 min~{s} x~{c}), "
       "using 1 minus the normalized value for criteria to be minimized."])

heading2("Accounting and output indicators", "6.8")
bullet("**Jobs:** plant jobs follow the eFAR intensities (Table 8) or technology benchmarks for new plants (1.6 FTE per "
       "1,000 m^{3} of mass timber; 5 FTE per 1,000 m^{3} of panels). Harvesting and hauling add 0.40 FTE per 1,000 m^{3}.")
bullet("**Indigenous income:** wages of Indigenous workers (regional labour share; 60% local hiring at "
       "Indigenous-majority plants; +15 percentage points at partnership plants; 80% at Indigenous-owned contractors), "
       "plus margins of Indigenous-owned contractors, plus the equity share of plant profits after capital charges. "
       "Equity losses are counted, so Indigenous investors carry downside risk.")
bullet("**Carbon:** net benefit = carbon stored in products (FORBIOM-ON storage factors) + fossil emissions avoided by "
       "bioheat (1.23 tCO~{2}e/odt replacing heating oil) \u2212 process, freight (0.00005 tCO~{2}/m^{3}\u00B7km) and "
       "harvest (0.012 tCO~{2}/m^{3}) emissions.")
bullet("**Residues:** sawmills generate 0.40 m^{3} of residue per m^{3} of logs (0.42 odt/m^{3}), of which 60% is "
       "already absorbed by pulp, composite and cogeneration uses. Harvesting yields 0.12 odt/m^{3} of forest residue, "
       "recoverable at $45/odt.")
bullet("**Recorded outputs:** annual records by FMU of harvest by fibre class, LTMD, products (lumber, mass timber, "
       "panels, OSB, pulp, bioheat, pellets), residue use, prices, plant counts, jobs, Indigenous jobs and income, value "
       "added, carbon and cumulative public cost, plus a registry of every new plant.")

heading2("Key parameters, sources and status", "6.9")
caption("Table", "Key FORBIOM-ABM parameters (2026 CAD, real).", keep_next=True)
data_table(["Parameter", "Value", "Source / basis", "Status"], [
    ["LTMD and harvest by FMU and fibre class", "Table 7", "ARWoodS 2025, FY2019\u20132024 means", "Calibrated"],
    ["Direct jobs per 1,000 m^{3} (sawmill; composite)", "0.41; 0.36", "eFAR 2020\u20132022", "Calibrated"],
    ["Harvest cost", "$38/m^{3} \u00D7 access factor 1.00\u20131.15", "FORBIOM-ON harvestCostRW", "Model-consistent"],
    ["In-region haul; stumpage", "110 km at $0.12/m^{3}\u00B7km; $6/m^{3}", "Ontario industry norms", "Assumption"],
    ["SPF lumber price (mill net)", "$300/m^{3}", "2023\u20132026 market range", "Assumption"],
    ["CLT/glulam price", "$1,100/m^{3} (\u00B120% tested)", "Industry quotes", "To validate"],
    ["Prefab panel price (wood equivalent)", "$1,300/m^{3}", "Industry estimates", "To validate"],
    ["OSB; pulpwood; residue; pellets", "$400/m^{3}; $70/m^{3}; $30/odt; $230/odt", "Market references", "Assumption"],
    ["Sawmill lumber recovery; residue fraction", "0.55; 0.40", "Boreal sawmill literature", "Literature"],
    ["Lumber per m^{3} CLT; per m^{3} panel", "1.20; 1.15", "FORBIOM-ON lumberInputPerUnit", "Model-consistent"],
    ["Southern mass-timber demand", "165,000 m^{3}/yr in 2026; growth 3/8/15%", "Scenario assumption", "Scenario"],
    ["Southern prefab panel demand", "60,000 m^{3}/yr in 2026", "Planning assumption", "To validate"],
    ["Northern housing need", "40\u2013150 units/yr per FMU at 35 m^{3}/unit, +2%/yr", "Planning assumption", "To validate"],
    ["Community heat demand", "3,000\u201310,000 odt/yr per FMU", "Planning assumption", "To validate"],
    ["Discount rates", "8% private; 4% social", "Standard practice", "Sensitivity (10%)"],
    ["Behaviour", "k = 12/4/5; expectation weight 0.3; price adjustment 0.3", "Set for plausible response",
     "Sensitivity-tested"],
], [2.0, 1.85, 1.55, 0.97], label_cols=1, left_cols=(1, 2, 3), size=7.5, group_fill=[None, MIST] * 8)
doc.add_paragraph().paragraph_format.space_after = Pt(2)

heading2("Coupling with FORBIOM-ON and limitations", "6.10")
body("The two models are currently soft-linked: they share regions, data and key parameters, but they are run "
     "separately. The planned co-evolutionary coupling (Figure 1) will exchange information once per period:")
bullet("**ABM to FORBIOM-ON:** effective harvest intensity by FMU (simulated harvest/LTMD), mass-timber adoption "
       "(installed hub and urban plant capacity), and supply and cost perturbations, written as GAMS parameter tables "
       "(CSV/GDX) that replace the current harvest caps, secondary capacities and stochastic multipliers.")
bullet("**FORBIOM-ON to ABM:** regional shadow prices of the sustainability and capacity constraints and optimal "
       "regional prices, which update agents' price expectations and investment screening in the next period.")
bullet("**Convergence:** the exchange is repeated within each period until harvest by FMU changes by less than a set "
       "tolerance, and then the models move to the next year.")
body("Current limitations: logs are sourced within each FMU (no cross-FMU log trade and no Manitoba or export markets "
     "for Kenora and Trout Lake), poplar and hardwood engineered-wood pathways are not yet represented, carbon "
     "accounting excludes forest carbon dynamics and construction-material substitution, and absolute values "
     "should be read as indicative for six FMUs rather than for all of Ontario.").paragraph_format.space_before = Pt(6)


# ---- Results section in a landscape block ----
land = doc.add_section(WD_SECTION.NEW_PAGE)
land.orientation = WD_ORIENT.LANDSCAPE
land.page_width, land.page_height = Inches(11.69), Inches(8.27)
for side, v in (("left_margin", 0.6), ("right_margin", 0.6), ("top_margin", 0.75), ("bottom_margin", 0.7)):
    setattr(land, side, Inches(v))
LAND_W = 11.69 - 1.2
header_footer(land, LAND_W)

heading1("7", "Results (from a preliminary counterfactual run)")

# Table 1 ------------------------------------------------------------------
T1 = {
    "Trout Lake": {
        "Primary": [
            "6.784 6.975 6.925 6.690 6.764 7.189 6.589 7.169 6.390 6.845 6.814",
            "1485.578 1709.211 1767.787 1629.459 1686.613 1889.770 1779.312 2044.070 1780.536 2078.378 1909.730",
            "508.568 557.896 544.155 479.960 470.609 500.285 452.121 492.863 410.823 455.563 397.284"],
        "Secondary": [
            "0.328 0.355 0.318 0.322 0.309 0.320 0.325 0.343 0.322 0.345 0.324",
            "210.395 232.832 215.877 224.800 222.626 236.611 246.206 271.739 260.546 288.186 277.846",
            "60.997 64.303 56.673 56.171 52.917 53.542 53.048 55.576 50.757 53.391 49.023"]},
    "Abitibi": {
        "Primary": [
            "11.616 12.101 11.157 11.083 10.539 11.236 11.595 11.281 11.377 10.561 11.492",
            "2293.021 2486.456 2518.225 2519.889 2407.424 2745.401 2807.892 2682.792 3165.977 2824.694 3221.283",
            "754.013 774.030 750.925 714.555 653.306 709.490 682.364 624.994 701.853 598.330 644.308"],
        "Secondary": [
            "0.332 0.318 0.323 0.319 0.334 0.359 0.309 0.343 0.341 0.340 0.328",
            "211.817 208.255 218.835 222.999 239.062 266.429 235.459 267.631 272.427 282.086 279.390",
            "61.464 57.525 57.465 55.708 56.892 60.236 50.676 54.875 53.190 52.329 49.347"]},
    "Algoma": {
        "Primary": [
            "9.440 10.956 9.348 9.634 9.066 9.721 9.034 9.326 10.150 10.322 9.416",
            "2015.356 2364.439 2036.564 2114.114 2080.283 2254.412 2213.542 2291.430 2772.758 2780.685 2519.347",
            "669.230 745.476 616.130 606.888 568.917 587.211 554.020 541.656 621.770 585.300 510.675"],
        "Secondary": [
            "0.310 0.350 0.336 0.335 0.320 0.347 0.366 0.344 0.361 0.301 0.329",
            "198.123 229.897 228.631 232.074 230.186 257.426 278.884 270.305 292.790 250.200 280.681",
            "57.482 63.458 59.984 58.077 54.710 58.225 60.035 55.356 57.015 46.394 49.559"]},
    "Kenora": {
        "Primary": [
            "4.692 4.918 5.383 4.994 4.973 5.100 4.698 5.122 5.025 5.199 5.061",
            "987.516 1185.063 1274.862 1198.432 1192.944 1274.638 1181.492 1422.141 1396.171 1505.040 1533.381",
            "356.695 400.434 406.536 366.464 344.442 356.995 317.041 351.570 334.654 341.777 328.491"],
        "Secondary": [
            "0.356 0.346 0.344 0.340 0.314 0.375 0.359 0.313 0.354 0.358 0.328",
            "225.237 226.894 234.760 235.804 224.037 277.347 272.470 246.774 288.170 297.771 279.273",
            "65.440 62.650 61.579 58.975 53.320 62.752 58.697 50.514 56.096 55.206 49.323"]},
    "Nipissing": {
        "Primary": [
            "14.585 13.502 12.654 14.545 13.050 15.197 13.125 13.085 13.442 13.701 13.912",
            "3162.500 2980.163 2867.236 3271.048 3151.354 3763.874 3225.851 3518.512 3615.353 3827.208 4077.295",
            "1026.065 928.593 850.473 919.744 842.545 952.030 782.299 815.248 794.776 799.076 805.231"],
        "Secondary": [
            "0.312 0.353 0.335 0.363 0.316 0.327 0.334 0.353 0.348 0.341 0.305",
            "198.481 230.641 224.345 252.285 226.557 241.027 256.575 278.740 281.855 285.293 260.610",
            "57.625 63.725 59.031 63.079 53.882 54.565 55.150 57.023 54.898 52.860 45.994"]},
    "Algonquin": {
        "Primary": [
            "8.555 8.445 8.089 8.343 8.241 8.267 8.266 8.563 8.837 8.515 7.606",
            "1763.905 1801.296 1890.919 1922.036 1904.388 2137.592 2139.879 2258.498 2401.540 2426.811 2153.606",
            "593.931 581.367 579.887 555.847 528.903 561.690 535.962 534.475 543.001 525.322 445.749"],
        "Secondary": [
            "0.340 0.366 0.348 0.321 0.353 0.335 0.339 0.323 0.351 0.366 0.342",
            "215.015 239.688 236.430 222.091 252.086 246.720 260.804 251.874 283.891 305.238 295.895",
            "62.497 66.196 62.061 55.570 59.992 55.864 56.056 51.656 55.320 56.573 52.128"]},
}
METRICS = ["Production (Mt)", "Revenue (M CAD)", "Processing cost (M CAD)"]
rows, merges, gstarts, lrules, gfill = [], [], [], [], []
for gi, (reg, streams) in enumerate(T1.items()):
    r0 = len(rows)
    gstarts.append(r0)
    for si, (stream, mets) in enumerate(streams.items()):
        s0 = len(rows)
        if si == 1:
            lrules.append((s0, 1))
        for mi, line in enumerate(mets):
            rows.append([reg if (si == 0 and mi == 0) else "", stream if mi == 0 else "", METRICS[mi]] + line.split())
            gfill.append(MIST if gi % 2 else None)
        merges.append((s0, 1, s0 + 2, 1))
    merges.append((r0, 0, r0 + 5, 0))

caption("Table", "Annual biomass production, revenue, and processing cost by region and manufacturing stream, "
                 "2020\u20132030 (FORBIOM-ON: Forest Biomass Ontario).", keep_next=True)
data_table(["Region", "Stream", "Metric"] + YEARS, rows, [0.95, 0.75, 1.45] + [0.665] * 11,
           merges=merges, group_starts=gstarts, light_rules=lrules, label_cols=3, bold_cols=(0,),
           group_fill=gfill, size=7, row_h=0.128)
notes([
    "**Regions:** Trout Lake, Abitibi, Algoma, Kenora, Nipissing, and Algonquin refer to forest management units in Ontario, Canada.",
    "**Streams:** *Primary* stream refers to first-stage industrial processing of roundwood into intermediate products "
    "(e.g., lumber), with co-products such as pulpwood, chips, and residues generated during transformation; *Secondary* "
    "stream refers to downstream manufacturing processes that further transform primary products (e.g., lumber) into "
    "higher-value engineered wood products, including cross-laminated timber (CLT) and glued laminated timber (glulam).",
    "**Metrics:** *Production* is the annual harvested biomass volume (Mt = megatonnes, i.e., millions of metric tons). "
    "*Revenue* is gross annual income from biomass sales. *Processing cost* is the annual cost of harvesting, "
    "transportation, and processing operations. Both financial metrics are in M CAD (millions of Canadian dollars, nominal values).",
    "**Scenario:** FORBIOM-ON = Forest Biomass Ontario model scenario, a simulation framework projecting sustainable "
    "forest biomass supply and economic outcomes under current and counterfactual harvest policies.",
])

# Table 2 ------------------------------------------------------------------
PRICES = {
    "CLT": "700.000 721.000 742.630 764.909 787.856 811.492 835.837 860.912 886.739 913.341 940.741 815.042 83.614",
    "Glulam": "575.000 592.250 610.017 628.318 647.168 666.583 686.580 707.177 728.393 750.245 772.752 669.862 68.678",
    "Lumber": "375.000 386.250 397.837 409.773 422.066 434.728 447.770 461.203 475.039 489.290 503.969 436.902 44.771",
    "Pulpwood": "75.000 77.250 79.567 81.955 84.413 86.946 89.554 92.241 95.008 97.858 100.794 87.326 8.954",
}
REGIONS = ["Trout Lake", "Abitibi", "Algoma", "Kenora", "Nipissing", "Algonquin"]
rows, merges, gstarts, gfill = [], [], [], []
for gi, reg in enumerate(REGIONS):
    r0 = len(rows)
    gstarts.append(r0)
    for pi, (prod, line) in enumerate(PRICES.items()):
        rows.append([reg if pi == 0 else "", prod] + line.split())
        gfill.append(MIST if gi % 2 else None)
    merges.append((r0, 0, r0 + 3, 0))
caption("Table", "Exogenous product price paths by region, 2020\u20132030. *CLT:* cross-laminated timber; *Glulam:* "
                 "glued laminated timber. All prices are in Canadian dollars per cubic metre (CAD/m^{3}). *Mean* and "
                 "*SD* (standard deviation) computed over 2020\u20132030 (*n* = 11).", keep_next=True, new_page=True)
data_table(["Region", "Product"] + YEARS + ["Mean", "SD"], rows, [0.95, 0.75] + [0.64] * 11 + [0.75, 0.68],
           merges=merges, group_starts=gstarts, label_cols=2, summary_from=13, group_fill=gfill,
           header2=["", ""] + [""] * 11 + ["($/m^{3})", "($/m^{3})"])
notes(["*Note:* *Lumber:* sawn structural wood; *Pulpwood:* roundwood for pulp and paper.",
       "Prices are exogenous model inputs. All prices are nominal."])

# Table 3 ------------------------------------------------------------------
STOCK = [
    ("Trout Lake", "28,992.2 31,260.3 33,618.8 35,552.0 37,575.6 39,689.1 41,893.8 44,188.2 46,574.0 48,533.6 50,583.8 39,860.1 7,069.4 5.71"),
    ("Abitibi", "107,762.9 114,901.9 122,378.1 130,190.5 138,339.7 146,824.4 155,644.8 162,883.6 170,458.4 178,370.2 186,617.3 146,852.0 26,017.2 5.64"),
    ("Algoma", "54,874.8 59,749.6 64,837.6 70,136.9 75,648.4 80,163.6 84,891.1 89,829.9 94,979.3 100,340.0 105,913.4 80,124.1 16,722.6 6.80"),
    ("Kenora", "49,741.2 53,677.5 57,771.5 61,121.6 64,630.0 68,296.3 72,121.3 76,103.9 80,244.8 83,641.3 87,196.0 68,595.0 12,216.6 5.78"),
    ("Nipissing", "45,246.1 48,977.8 52,888.4 56,975.0 61,241.3 65,683.3 70,305.6 74,090.1 78,052.2 82,192.1 86,509.8 65,651.1 13,888.9 6.69"),
    ("Algonquin", "36,716.1 40,035.1 43,500.0 47,110.2 50,866.1 53,936.9 57,153.3 60,514.9 64,021.8 67,674.6 71,474.0 54,818.5 11,366.9 6.88"),
    ("Total", "323,333.3 348,602.2 374,894.6 401,086.3 428,321.0 454,593.6 482,003.6 507,614.5 535,330.5 560,751.9 588,294.1 455,893.2 86,143.0 6.16"),
]
caption("Table", "Roundwood standing stock by region, 2020\u20132030 (million m^{3}). *SD:* standard deviation of the "
                 "11 annual stock levels; *CAGR (%):* compound annual growth rate from 2020 to 2030.", keep_next=True,
        new_page=True)
data_table(["Region"] + YEARS + ["Mean", "SD", "CAGR (%)"], [[r] + v.split() for r, v in STOCK],
           [0.95] + [0.68] * 11 + [0.72, 0.66, 0.6], summary_from=12, total_rows=(6,), size=7.5,
           group_fill=[None, MIST, None, MIST, None, MIST, None])
notes(["Regions are forest management units (FMUs) in Ontario, Canada.",
       "*Mean* and *SD* computed over *n* = 11 years (2020\u20132030); SD uses the population formula.",
       "*CAGR* uses the 2020 and 2030 endpoint values over a 10-year span.",
       "Commas denote thousands separators (e.g., 28,992 = 28 992)."])

# Table 4 ------------------------------------------------------------------
HARV = [
    ("Trout Lake", "7.261 7.507 7.455 7.168 7.242 7.708 7.067 7.700 6.842 7.356 7.270 7.325 0.252"),
    ("Abitibi", "12.326 12.845 11.892 11.797 11.205 11.974 12.320 11.960 12.151 11.236 12.234 12.000 0.468"),
    ("Algoma", "10.068 11.671 9.951 10.241 9.646 10.332 9.621 9.913 10.836 10.982 10.004 10.297 0.587"),
    ("Kenora", "5.026 5.299 5.779 5.359 5.323 5.470 5.033 5.501 5.393 5.583 5.437 5.382 0.210"),
    ("Nipissing", "15.549 14.392 13.486 15.464 13.908 16.186 13.956 13.966 14.320 14.601 14.837 14.606 0.826"),
    ("Algonquin", "9.113 9.002 8.655 8.898 8.780 8.849 8.834 9.141 9.436 9.106 8.118 8.994 0.330"),
    ("Total", "59.343 60.716 57.218 58.927 56.104 60.519 56.831 57.181 59.014 58.864 57.900 58.602 1.456"),
]
caption("Table", "Roundwood harvest by region, 2020\u20132030 (million m^{3}). *SD:* standard deviation of the 11 annual "
                 "harvest volumes; *Mean:* average annual harvest over 2020\u20132030.", keep_next=True)
data_table(["Region"] + YEARS + ["Mean", "SD"], [[r] + v.split() for r, v in HARV],
           [1.0] + [0.72] * 11 + [0.75, 0.7], summary_from=12, total_rows=(6,), size=8,
           group_fill=[None, MIST, None, MIST, None, MIST, None])
notes(["Regions are forest management units (FMUs) in Ontario, Canada.",
       "*Mean* and *SD* computed over *n* = 11 years (2020\u20132030); SD uses the population formula.",
       "All harvest volumes are in million cubic metres (million m^{3}) per year."])

# Table 5 ------------------------------------------------------------------
PROD = {
    "Trout Lake": [
        "0.173 0.175 0.165 0.164 0.160 0.160 0.155 0.188 0.165 0.182 0.162 0.168 0.011",
        "0.155 0.180 0.152 0.158 0.150 0.161 0.170 0.156 0.157 0.163 0.163 0.161 0.009",
        "3.729 4.298 4.281 3.761 3.749 4.097 3.786 4.244 3.551 4.095 3.500 3.917 0.276",
        "3.055 2.677 2.644 2.929 3.014 3.093 2.803 2.925 2.839 2.750 3.314 2.913 0.198"],
    "Abitibi": [
        "0.167 0.155 0.165 0.165 0.161 0.188 0.157 0.162 0.153 0.166 0.154 0.163 0.010",
        "0.165 0.163 0.157 0.154 0.174 0.170 0.151 0.182 0.188 0.174 0.174 0.169 0.012",
        "5.217 5.478 5.587 5.375 4.975 5.602 5.384 4.943 5.974 5.064 5.587 5.381 0.298",
        "6.399 6.623 5.570 5.708 5.564 5.635 6.211 6.338 5.403 5.497 5.905 5.987 0.401"],
    "Algoma": [
        "0.157 0.178 0.181 0.156 0.165 0.178 0.184 0.175 0.189 0.151 0.157 0.170 0.014",
        "0.153 0.172 0.155 0.180 0.154 0.170 0.182 0.170 0.171 0.150 0.172 0.166 0.011",
        "4.804 5.416 4.546 4.521 4.355 4.552 4.447 4.374 5.278 4.956 4.367 4.692 0.337",
        "4.635 5.541 4.803 5.113 4.711 5.169 4.586 4.952 4.872 5.367 5.049 4.982 0.289"],
    "Kenora": [
        "0.166 0.172 0.188 0.164 0.150 0.188 0.173 0.163 0.190 0.181 0.154 0.172 0.014",
        "0.190 0.173 0.156 0.176 0.164 0.187 0.186 0.150 0.165 0.177 0.174 0.173 0.013",
        "2.629 3.103 3.156 2.895 2.740 2.929 2.639 3.025 2.929 3.059 3.008 2.920 0.178",
        "2.063 1.815 2.226 2.099 2.233 2.170 2.058 2.097 2.096 2.140 2.053 2.095 0.109"],
    "Nipissing": [
        "0.152 0.169 0.152 0.178 0.158 0.159 0.183 0.190 0.180 0.179 0.150 0.168 0.015",
        "0.160 0.183 0.183 0.185 0.158 0.168 0.151 0.163 0.168 0.162 0.155 0.167 0.012",
        "7.344 6.775 6.325 6.863 6.525 7.493 6.206 6.774 6.653 6.844 7.073 6.807 0.348",
        "7.241 6.727 6.329 7.682 6.525 7.704 6.919 6.311 6.789 6.857 6.839 6.902 0.430"],
    "Algonquin": [
        "0.154 0.180 0.182 0.151 0.169 0.161 0.186 0.150 0.177 0.188 0.186 0.171 0.015",
        "0.186 0.185 0.166 0.170 0.184 0.174 0.153 0.173 0.174 0.177 0.156 0.173 0.011",
        "4.228 4.243 4.420 4.237 4.086 4.561 4.397 4.444 4.615 4.598 3.934 4.342 0.193",
        "4.326 4.202 3.669 4.106 4.155 3.707 3.869 4.119 4.222 3.917 3.671 3.997 0.225"],
}
rows, merges, gstarts, gfill = [], [], [], []
for gi, (reg, lines) in enumerate(PROD.items()):
    r0 = len(rows)
    gstarts.append(r0)
    for pi, (prod, line) in enumerate(zip(["CLT", "Glulam", "Lumber", "Pulpwood"], lines)):
        rows.append([reg if pi == 0 else "", prod] + line.split())
        gfill.append(MIST if gi % 2 else None)
    merges.append((r0, 0, r0 + 3, 0))
caption("Table", "Output production by region and product, 2020\u20132030 (million m^{3}).", keep_next=True,
        new_page=True)
data_table(["Region", "Product"] + YEARS + ["Mean", "SD"], rows, [0.95, 0.75] + [0.64] * 11 + [0.75, 0.68],
           merges=merges, group_starts=gstarts, label_cols=2, summary_from=13, group_fill=gfill)
notes(["*Note:* Output production in million m^{3}.",
       "Mean and SD computed over 2020\u20132030 (*n* = 11, population formula)."])

# --------------------------------------------------------------------------
# Back to portrait for scenario results and figures
# --------------------------------------------------------------------------
port = doc.add_section(WD_SECTION.NEW_PAGE)
port.orientation = WD_ORIENT.PORTRAIT
port.page_width, port.page_height = Inches(8.27), Inches(11.69)
for side in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
    setattr(port, side, Inches(0.95))
header_footer(port, TEXT_W)

DEM_Q = {
    "Baseline": "3,612.066 3,646.042 3,699.067 3,786.401 3,685.933 3,784.808",
    "D10": "3,973.272 4,010.647 4,068.973 4,165.042 4,054.527 4,163.289",
    "D50": "5,418.098 5,469.064 5,548.600 5,679.602 5,528.900 5,677.213",
    "D100": "7,224.131 7,292.085 7,398.133 7,572.803 7,371.867 7,569.617",
    "D200": "10,836.197 10,938.127 11,097.200 11,359.204 11,057.800 11,354.425",
    "D300": "14,448.262 14,584.169 14,796.267 15,145.606 14,743.733 15,139.234",
    "D400": "18,060.328 18,230.212 18,495.333 18,932.007 18,429.667 18,924.042",
}
DEM_R = {
    "Baseline": "2,687.664 2,704.390 2,749.197 2,808.537 2,736.410 2,809.732",
    "D10": "2,956.430 2,974.829 3,024.117 3,089.390 3,010.051 3,090.706",
    "D50": "4,031.496 4,056.586 4,123.795 4,212.805 4,104.615 4,214.599",
    "D100": "5,375.328 5,408.781 5,498.394 5,617.073 5,472.819 5,619.465",
    "D200": "8,062.992 8,113.171 8,247.591 8,425.610 8,209.229 8,429.197",
    "D300": "10,750.656 10,817.562 10,996.788 11,234.147 10,945.639 11,238.930",
    "D400": "13,438.319 13,521.952 13,745.985 14,042.683 13,682.049 14,048.662",
}
rows, gfill = [], []
for label, data in (("Quantity (1,000 m^{3})", DEM_Q), ("Revenue (M CAD)", DEM_R)):
    for i, (sc, line) in enumerate(data.items()):
        rows.append([label if i == 0 else "", sc] + line.split())
        gfill.append(None if label.startswith("Q") else MIST)
caption("Table", "Cumulative mass timber demand and revenue by region and scenario, 2020\u20132030 (FORBIOM-ON). "
                 "*CLT:* cross-laminated timber; *Glulam:* glued laminated timber; *M CAD:* millions of Canadian "
                 "dollars. *Baseline:* reference mass-timber demand caps; *D10\u2013D400:* percentage increase in the "
                 "demand cap relative to the baseline.", keep_next=True)
DEM_TAB = SEQ["Table"]
data_table(["Variable", "Scenario"] + REGIONS, rows, [1.15, 0.72] + [0.75] * 6,
           merges=[(0, 0, 6, 0), (7, 0, 13, 0)], group_starts=(0, 7), light_rules=[(1, 1), (8, 1)],
           label_cols=2, size=8.5, group_fill=gfill)
notes(["Regions are forest management units (FMUs) in Ontario, Canada.",
       "*Quantity* is the cumulative CLT + Glulam demand over 2020\u20132030, in thousands of cubic metres "
       "(1,000 m^{3}). *Revenue* is the corresponding cumulative revenue, in millions of Canadian dollars (M CAD).",
       "*Scenarios:* *Baseline* uses reference mass-timber demand caps; *D10\u2013D400* denote percentage increases in "
       "the demand cap relative to the baseline (e.g., D100 = 100% increase).",
       "Commas denote thousands separators."])

figure(os.path.join(HERE, "Q8.png"), 6.37,
       "Spatial\u2013temporal roundwood harvest pattern by demand scenario, 2020\u20132030 (FORBIOM-ON). Each panel is a "
       "heatmap of annual harvest volumes (million m^{3}/yr) across six Ontario forest management units (FMUs) and "
       "eleven years (2020\u20132030). Colour intensity indicates harvest level: darker blue = higher harvest. "
       "*Regions (rows):* TL = Trout Lake; AB = Abitibi; AL = Algoma; KE = Kenora; NI = Nipissing; AQ = Algonquin. "
       "*Scenarios:* Baseline = reference mass-timber demand caps; D10\u2013D400 = percentage increase in the demand "
       "cap relative to the baseline.")

figure(os.path.join(HERE, "Q9.png"), 4.9,
       "Stock trends by region and product type, 2020\u20132035 (thousands of m^{3} per year).")

caption("Table", "Model objective value and carbon cost under alternative carbon-price scenarios. **Scenario codes** "
                 "(*cp*x): carbon price set to x Canadian dollars per tonne CO~{2} equivalent (CAD/tCO~{2}e), e.g., "
                 "*cp*50 = 50 CAD/tCO~{2}e; *cp*0 = no carbon price. **Obj:** value of the optimization objective "
                 "(million CAD). **Carbon cost:** aggregate carbon cost term implied by the carbon price in the run "
                 "(million CAD); \u201C\u2014\u201D indicates not applicable at zero carbon price.", keep_next=True)
CP = [("cp0", "\u2014", "99,011.678"), ("cp50", "1,328.095", "97,683.458"), ("cp100", "2,656.190", "96,355.363"),
      ("cp170", "4,515.523", "94,496.030"), ("cp250", "6,640.476", "92,371.078"), ("cp350", "9,296.666", "89,714.888"),
      ("cp500", "13,280.951", "85,730.602")]
data_table(["Carbon price scenario", "Carbon cost (M CAD)", "Obj (M CAD)"], [list(r) for r in CP],
           [2.0, 1.8, 1.8], label_cols=1, size=9.5, group_fill=[None, MIST] * 3 + [None])
doc.add_paragraph().paragraph_format.space_after = Pt(4)

figure(os.path.join(HERE, "Q6.png"), 6.3,
       "Cumulative mass timber output (CLT + Glulam) by region and demand scenario, 2020\u20132030 (1,000 m^{3}). "
       "**CLT:** cross-laminated timber; **Glulam:** glued laminated timber. Scenario labels (e.g., D50) correspond to "
       f"mass-timber demand-cap multipliers described in the demand scenario table (Table {DEM_TAB}).")

pair = doc.add_table(rows=1, cols=2)
pair.alignment = WD_TABLE_ALIGNMENT.CENTER
set_table_borders(pair)
set_col_widths(pair, [3.18, 3.18])
for cell, img, cap in (
        (pair.cell(0, 0), "Q4.png", "Total revenue by region, cumulative over 2020\u20132030. **M CAD:** millions of Canadian dollars."),
        (pair.cell(0, 1), "Q5.png", "Regional revenue in the year 2025. **M CAD:** millions of Canadian dollars.")):
    set_cell_margins(cell, left=60, right=60)
    p = cell.paragraphs[0]
    pfmt(p, before=8, after=0, align=WD_ALIGN_PARAGRAPH.CENTER, keep_next=True, line=1.0)
    path = os.path.join(HERE, img)
    p.add_run().add_picture(path if os.path.exists(path) else PH_SIDE_A, height=Inches(1.75))
    caption("Figure", cap, container=cell, align=WD_ALIGN_PARAGRAPH.LEFT)

# ---- Supplementary materials ----
p = doc.add_paragraph(style="Heading 1")
p.add_run("Supplementary materials (code, data, scripts)")
box = callout(fill=MIST, bar=PINE)
items = [
    ("GitHub repository", f"Full shareable package (report, GAMS, ABM, scripts, derived data, figures, appendix): "
                          f"[**{GITHUB_URL}**]({GITHUB_URL})."),
    ("Key code", f"`gams/SA15.gms` and `gams/FORBIOM_ON.gms` in the repository "
                 f"(also mirrored [on Google Drive]({DRIVE_URL}))."),
    ("Data", "Derived CSV calibration and result tables are in `abm/calibration/`, `abm/results/` and "
             "`data/gams_outputs/`. Raw FRI geodatabases and large GDX binaries are omitted; "
             "CRIBE ArcGIS, GeoHub stocks and Plonski yield tables remain with their providers."),
    ("Scripts", f"Python FRI processing, mapping and the DOCX builder are under `scripts/` "
                f"([Drive mirror]({DRIVE_URL}))."),
    ("Appendix", "See **Appendix A** below and `docs/APPENDIX.md` in the repository for the file map "
                 "and reproduction notes. Extended ABM docs are in `docs/`."),
]
for i, (lab, txt) in enumerate(items):
    p = box.paragraphs[0] if i == 0 else box.add_paragraph()
    pfmt(p, after=6 if i < len(items) - 1 else 0, left=1.0, first=-1.0)
    p.paragraph_format.tab_stops.add_tab_stop(Inches(1.35))
    fmt_run(p.add_run(lab), color=FOREST, bold=True)
    p.add_run("\t")
    add_rich(p, txt)

# ---- Appendix A ----
heading1("A", "Appendix \u2014 Shareable repository contents")
body(f"This appendix catalogues the public GitHub repository that accompanies the report. "
     f"Clone or browse it at [{GITHUB_URL}]({GITHUB_URL}). The package is curated for sharing: "
     f"model code, derived tables and the report are included; raw MNR extracts, FRI geodatabases "
     f"and personal working files from the project archive are not.")

heading2("Repository layout", num="A.1")
data_table(
    ["Path", "Contents"],
    [
        ["`report/`", "Preliminary-results DOCX and PDF"],
        ["`gams/`", "`SA15.gms`, `FORBIOM_ON.gms`, eFAR bridge scripts"],
        ["`abm/`", "FORBIOM-ABM Python modules, calibration CSVs, summary tables"],
        ["`scripts/`", "FRI processing, report builder, mapping utilities"],
        ["`data/`", "Model-ready eFAR bridge CSVs and GAMS summary outputs"],
        ["`figures/`", "PNG figures used in this report"],
        ["`docs/`", "Appendix guide and extended ABM DOCX reports"],
        ["`README.md`", "Overview, quick start and citation"],
    ],
    widths=[1.55, 4.85],
    size=8.5, row_h=0.22, left_cols=(0, 1),
)

heading2("Reproduction pointers", num="A.2")
bullet(f"**GAMS counterfactual (Section 7 tables):** run [`gams/SA15.gms`]({GITHUB_URL}/blob/main/gams/SA15.gms) "
       "in GAMS with an NLP solver (e.g. CONOPT).")
bullet(f"**ABM calibration tables:** [`abm/calibrate.py`]({GITHUB_URL}/blob/main/abm/calibrate.py) "
       "(requires local ARWoodS / eFAR extracts; derived CSVs are already in `abm/calibration/`).")
bullet(f"**ABM strategies S0\u2013S6:** [`abm/experiments.py`]({GITHUB_URL}/blob/main/abm/experiments.py) "
       "then `analysis.py` / `figures.py`.")
bullet(f"**Regenerate this DOCX:** [`scripts/build_forbiom_report_docx.py`]({GITHUB_URL}/blob/main/scripts/build_forbiom_report_docx.py) "
       "(Python 3.11+, `python-docx`, Pillow; Microsoft Word optional to refresh the TOC).")

heading2("Data and redistribution limits", num="A.3")
bullet("**Included:** derived calibration CSVs, GAMS/ABM summary CSV/TXT outputs, model source, report and figures.")
bullet("**Not redistributed:** raw ARWoodS/eFAR extracts (Ontario MNR), FRI FIM v2 geodatabases, large `*.gdx` / `*.gpkg` binaries.")
bullet("**Status flags:** stock units, FRI biomass coefficients and several logistics capacities remain provisional "
       "(see Sections 5.5 and 6.10).")

heading2("Citation", num="A.4")
body("Yousefpour, R. & Elfahli, Y. (2026). *Ontario Forest Biomass: Supply Chain Feasibility, Processing "
     "Optimization, and ABM-Integrated Biomass Utilization* (FORBIOM-ON preliminary results). "
     f"Code and data package: {GITHUB_URL}.")

doc.save(OUT)
print("Saved", OUT)
print("GitHub URL used:", GITHUB_URL)
