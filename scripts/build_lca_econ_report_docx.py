"""Life-cycle and economic-impact report. Inventory stage: no characterized scores."""
import os
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Pt, Inches, RGBColor, Twips

HERE = os.path.dirname(os.path.abspath(__file__))
# Support running from the project root or from FORBIOM-ON-shareable/scripts/.
ROOT = HERE if os.path.isdir(os.path.join(HERE, "abm")) else (
    os.path.dirname(HERE) if os.path.isdir(os.path.join(os.path.dirname(HERE), "abm")) else HERE
)
REPORT_DIR = os.path.join(ROOT, "report") if os.path.isdir(os.path.join(ROOT, "report")) else ROOT
os.makedirs(REPORT_DIR, exist_ok=True)
OUT = os.path.join(REPORT_DIR, "FORBIOM-ON_Activity4_LCA_Economic_Impact_Report.docx")
if REPORT_DIR == ROOT:
    OUT = os.path.join(ROOT, "FORBIOM-ON_Activity4_LCA_Economic_Impact_Report_v4.docx")

FOREST, PINE, SAGE, MIST = "1B4332", "2D6A4F", "E8F0EA", "F4F8F5"
GOLD, GOLD_LIGHT, INK, GREY, RULE = "C9A227", "FBF6E9", "1F2A24", "5F6B64", "A9C5B1"
BODY_FONT, HEAD_FONT = "Calibri", "Georgia"
DATE_TEXT = "October 27, 2026"
GITHUB_URL = os.environ.get(
    "FORBIOM_GITHUB_URL",
    "https://github.com/yassirelfahli/forbiom-on",
)


def rgb(h):
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _get_or_add(parent, tag):
    el = parent.find(qn(tag))
    if el is None:
        el = OxmlElement(tag)
        parent.append(el)
    return el


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


def para_border(p, edge, sz, color, space=4):
    pPr = p._p.get_or_add_pPr()
    pbdr = _get_or_add(pPr, "w:pBdr")
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:space"), str(space))
    el.set(qn("w:color"), color)
    pbdr.append(el)


def char_spacing(run, twips):
    rPr = run._r.get_or_add_rPr()
    sp = OxmlElement("w:spacing")
    sp.set(qn("w:val"), str(twips))
    rPr.append(sp)


def set_cell_bg(cell, color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcPr.append(shd)


def set_cell_margins(cell, top=40, bottom=40, left=60, right=60):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for edge, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcPr.append(mar)


def set_col_widths(table, widths):
    table.autofit = False
    table.allow_autofit = False
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement("w:tblPr")
    tblW = OxmlElement("w:tblW")
    total = int(sum(widths) * 1440)
    tblW.set(qn("w:w"), str(total))
    tblW.set(qn("w:type"), "dxa")
    tblPr.append(tblW)
    grid = tbl.find(qn("w:tblGrid"))
    if grid is not None:
        tbl.remove(grid)
    grid = OxmlElement("w:tblGrid")
    for w in widths:
        gc = OxmlElement("w:gridCol")
        gc.set(qn("w:w"), str(int(w * 1440)))
        grid.append(gc)
    tblPr.addnext(grid)
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            tcW = OxmlElement("w:tcW")
            tcW.set(qn("w:w"), str(int(widths[i] * 1440)))
            tcW.set(qn("w:type"), "dxa")
            tcPr.append(tcW)


def set_table_borders(table):
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tblPr.append(borders)


def shade_header(row):
    for cell in row.cells:
        set_cell_bg(cell, FOREST)


doc = Document()
doc.core_properties.title = (
    "Environmental Life Cycle Assessment and Economic Impact of Biomass-Based Construction Products"
)
doc.core_properties.subject = "FORBIOM-ON life cycle assessment and economic impact, inventory stage"
doc.core_properties.author = "Rasoul Yousefpour; Yasser Elfahli"
doc.core_properties.keywords = "FORBIOM-ON, life cycle assessment, economic impact, mass timber, Ontario"

normal = doc.styles["Normal"]
normal.font.name = BODY_FONT
normal.font.size = Pt(11)
normal.font.color.rgb = rgb(INK)
normal.paragraph_format.space_after = Pt(8)
normal.paragraph_format.line_spacing = 1.12

from docx.enum.style import WD_STYLE_TYPE

h1 = doc.styles["Heading 1"]
h1.font.name = HEAD_FONT
h1.font.size = Pt(16)
h1.font.bold = True
h1.font.color.rgb = rgb(FOREST)
h1.paragraph_format.space_before = Pt(16)
h1.paragraph_format.space_after = Pt(6)
h1.paragraph_format.keep_with_next = True

fn_text = doc.styles.add_style("Footnote Text", WD_STYLE_TYPE.PARAGRAPH)
fn_text.element.set(qn("w:styleId"), "FootnoteText")
fn_text.font.name = BODY_FONT
fn_text.font.size = Pt(10)
fn_text.font.color.rgb = rgb(INK)
fn_text.paragraph_format.space_before = Pt(0)
fn_text.paragraph_format.space_after = Pt(0)
fn_text.paragraph_format.line_spacing = 1.0
fn_ref = doc.styles.add_style("Footnote Reference", WD_STYLE_TYPE.CHARACTER)
fn_ref.element.set(qn("w:styleId"), "FootnoteReference")
fn_ref.font.name = BODY_FONT
fn_ref.font.size = Pt(10)
fn_ref.font.color.rgb = rgb(INK)
_rPr = fn_ref.element.get_or_add_rPr()
_va = OxmlElement("w:vertAlign")
_va.set(qn("w:val"), "superscript")
_rPr.append(_va)

for lvl, size in (("TOC 1", 11), ("TOC 2", 10.5)):
    try:
        st = doc.styles[lvl]
    except KeyError:
        st = doc.styles.add_style(lvl, WD_STYLE_TYPE.PARAGRAPH)
    st.font.name = BODY_FONT
    st.font.size = Pt(size)
    st.font.color.rgb = rgb(FOREST if lvl == "TOC 1" else INK)
    st.font.bold = lvl == "TOC 1"
    st.paragraph_format.space_before = Pt(4 if lvl == "TOC 1" else 1)
    st.paragraph_format.space_after = Pt(1)


XREF = re.compile(
    r"(?:Figures?|Tables?)\s+\d+"
    r"|Sections?\s+\d+(?:\.\d+)?(?:\s*(?:\u2013|\u2014|-|and|to)\s*\d+(?:\.\d+)?)*"
)


def add_rich(p, text, size=None, color=None, bold=False, italic=False, font=None):
    def emit(chunk, b, i, col):
        if not chunk:
            return
        r = p.add_run(chunk)
        fmt_run(r, size=size, color=col, bold=b or None, italic=i or None, font=font)

    pos = 0
    parts = re.split(r"(\*\*.+?\*\*|\*.+?\*)", text)
    for part in parts:
        if not part:
            continue
        b, i, chunk = bold, italic, part
        if part.startswith("**") and part.endswith("**"):
            chunk, b = part[2:-2], True
        elif part.startswith("*") and part.endswith("*"):
            chunk, i = part[1:-1], True
        cursor = 0
        for m in XREF.finditer(chunk):
            if m.start() > cursor:
                emit(chunk[cursor:m.start()], b, i, color)
            emit(m.group(0), b, i, PINE)
            cursor = m.end()
        if cursor < len(chunk):
            emit(chunk[cursor:], b, i, color)


def body(text):
    p = doc.add_paragraph()
    pfmt(p, after=8, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    add_rich(p, text)
    return p


def heading1(num, text):
    p = doc.add_paragraph(style="Heading 1")
    fmt_run(p.add_run(f"{num}   "), color=GOLD, font=HEAD_FONT, size=16, bold=True)
    p.add_run(text)
    para_border(p, "bottom", 8, GOLD, 3)
    return p


def heading3(text):
    p = doc.add_paragraph()
    pfmt(p, before=10, after=2, keep_next=True)
    fmt_run(p.add_run(text), size=12, color=FOREST, bold=True, font=HEAD_FONT)
    return p


def bullet(text):
    p = doc.add_paragraph()
    pfmt(p, after=3, left=0.28, first=-0.18, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    fmt_run(p.add_run("\u25A0  "), size=8, color=GOLD)
    add_rich(p, text)
    return p


def caption(text):
    p = doc.add_paragraph()
    pfmt(p, before=8, after=3, keep_next=True)
    add_rich(p, text, size=9, color=FOREST, bold=False)
    return p


def simple_table(header, rows, widths, size=8.5):
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(t)
    set_col_widths(t, widths)
    for i, h in enumerate(header):
        cell = t.rows[0].cells[i]
        set_cell_bg(cell, FOREST)
        set_cell_margins(cell, 50, 50, 70, 70)
        p = cell.paragraphs[0]
        pfmt(p, after=0, line=1.0)
        fmt_run(p.add_run(h), size=size, color="FFFFFF", bold=True)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = t.rows[r + 1].cells[c]
            if r % 2:
                set_cell_bg(cell, MIST)
            set_cell_margins(cell, 40, 40, 70, 70)
            p = cell.paragraphs[0]
            pfmt(p, after=0, line=1.0)
            fmt_run(p.add_run(val), size=size, color=INK, bold=(c == 0))
    return t


_FN = {"part": None, "n": 1}


def footnote(paragraph, text):
    reltype = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"
    if _FN["part"] is None:
        from docx.opc.packuri import PackURI
        from docx.opc.part import XmlPart
        root = parse_xml(
            '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
            '<w:footnote w:type="continuationSeparator" w:id="0">'
            '<w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>'
            "</w:footnotes>"
        )
        part = XmlPart(
            PackURI("/word/footnotes.xml"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml",
            root,
            doc.part.package,
        )
        doc.part.relate_to(part, reltype)
        _FN["part"] = part
    fid = str(_FN["n"])
    _FN["n"] += 1
    fn = OxmlElement("w:footnote")
    fn.set(qn("w:id"), fid)
    fp = OxmlElement("w:p")
    pPr = OxmlElement("w:pPr")
    ps = OxmlElement("w:pStyle")
    ps.set(qn("w:val"), "FootnoteText")
    pPr.append(ps)
    fp.append(pPr)
    r0 = OxmlElement("w:r")
    rPr0 = OxmlElement("w:rPr")
    rs = OxmlElement("w:rStyle")
    rs.set(qn("w:val"), "FootnoteReference")
    rPr0.append(rs)
    r0.append(rPr0)
    r0.append(OxmlElement("w:footnoteRef"))
    fp.append(r0)
    r1 = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = " " + text
    r1.append(t)
    fp.append(r1)
    fn.append(fp)
    _FN["part"].element.append(fn)
    run = paragraph.add_run()
    rPr = run._r.get_or_add_rPr()
    rs = OxmlElement("w:rStyle")
    rs.set(qn("w:val"), "FootnoteReference")
    rPr.append(rs)
    ref = OxmlElement("w:footnoteReference")
    ref.set(qn("w:id"), fid)
    run._r.append(ref)


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
    if size is not None:
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(size * 2)))
        rPr.append(sz)
        szCs = OxmlElement("w:szCs")
        szCs.set(qn("w:val"), str(int(size * 2)))
        rPr.append(szCs)
    rFonts = OxmlElement("w:rFonts")
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        rFonts.set(qn(a), BODY_FONT)
    rPr.append(rFonts)
    r.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    r.append(t)
    h.append(r)
    p._p.append(h)
    return h


def header_footer(section):
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    section.header_distance = Inches(0.4)
    section.footer_distance = Inches(0.4)
    hp = section.header.paragraphs[0]
    hp.text = ""
    pfmt(hp, after=0, line=1.0)
    hp.paragraph_format.tab_stops.add_tab_stop(Inches(6.35), WD_TAB_ALIGNMENT.RIGHT)
    r = fmt_run(hp.add_run("Life cycle assessment"), size=8.5, color=FOREST, bold=True)
    char_spacing(r, 30)
    fmt_run(hp.add_run("\tEconomic impact"), size=8.5, color=GREY)
    para_border(hp, "bottom", 6, GOLD, 4)
    fp = section.footer.paragraphs[0]
    fp.text = ""
    pfmt(fp, after=0, line=1.0)
    fp.paragraph_format.tab_stops.add_tab_stop(Inches(6.35), WD_TAB_ALIGNMENT.RIGHT)
    para_border(fp, "top", 4, RULE, 4)
    fmt_run(fp.add_run("R. Yousefpour  \u00B7  Y. Elfahli"), size=8, color=GREY)
    fmt_run(fp.add_run("\t"), size=8.5)
    add_field(fp, "PAGE", "1", size=9, color=FOREST, bold=True)


# --------------------------------------------------------------------------
# Cover
# --------------------------------------------------------------------------
cov = doc.sections[0]
cov.page_width, cov.page_height = Inches(8.27), Inches(11.69)
for side in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
    setattr(cov, side, Inches(0.5))

ct = doc.add_table(rows=1, cols=3)
set_table_borders(ct)
set_col_widths(ct, [1.15, 0.08, 6.04])
row = ct.rows[0]
row.height = Twips(15100)
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
r = fmt_run(sp.add_run("ONTARIO"), size=26, color="FFFFFF", bold=True, font=HEAD_FONT)
char_spacing(r, 40)
r = fmt_run(sp.add_run(" FOREST"), size=26, color=GOLD, bold=True, font=HEAD_FONT)
r = fmt_run(sp.add_run("    BIOMASS AND MASS TIMBER"), size=11, color="CFE1D5")

set_cell_margins(main_c, top=700, bottom=280, left=420, right=280)
p = main_c.paragraphs[0]
pfmt(p, after=0, line=1.0)
r = fmt_run(p.add_run("LIFE CYCLE ASSESSMENT"), size=10, color=PINE, bold=True)
char_spacing(r, 40)
r = fmt_run(p.add_run("    |    " + DATE_TEXT.upper()), size=10, color=GOLD, bold=True)

p = main_c.add_paragraph()
pfmt(p, before=28, after=0, line=0.95)
fmt_run(p.add_run("Environmental Life Cycle"), size=26, color=FOREST, bold=True, font=HEAD_FONT)
p = main_c.add_paragraph()
pfmt(p, before=2, after=0, line=0.95)
fmt_run(p.add_run("Assessment and Economic"), size=26, color=FOREST, bold=True, font=HEAD_FONT)
p = main_c.add_paragraph()
pfmt(p, before=2, after=0, line=0.95)
fmt_run(p.add_run("Impact"), size=26, color=FOREST, bold=True, font=HEAD_FONT)

p = main_c.add_paragraph()
pfmt(p, before=14, after=0, line=1.05)
fmt_run(
    p.add_run("Carbon offset potential and economic benefits of biomass-based construction products in six Ontario forest management units."),
    size=13, color=PINE, font=HEAD_FONT,
)

p = main_c.add_paragraph()
pfmt(p, before=16, after=0, line=1.0)
para_border(p, "top", 16, GOLD, 8)
fmt_run(p.add_run("Inventory-stage assessment  \u00B7  no characterized scores"), size=11, color=GREY, italic=True)

p = main_c.add_paragraph()
pfmt(p, before=10, after=0, line=1.05)
fmt_run(
    p.add_run(
        "An inventory-stage assessment of carbon-offset potential and economic benefits of biomass-based "
        "construction products. The assessment is complete as a goal, system boundary, foreground inventory, "
        "and direct economic account. It does not report characterized life-cycle scores or indirect economic multipliers."
    ),
    size=11, color=INK,
)

p = main_c.add_paragraph()
pfmt(p, before=36, after=0, line=1.0)
fmt_run(p.add_run("PREPARED BY"), size=8.5, color=GOLD, bold=True)
for name in ("Rasoul Yousefpour", "Yasser Elfahli"):
    p = main_c.add_paragraph()
    pfmt(p, before=2, after=0, line=1.0)
    fmt_run(p.add_run(name), size=13, color=FOREST, bold=True, font=HEAD_FONT)
p = main_c.add_paragraph()
pfmt(p, before=6, after=0)
fmt_run(p.add_run(DATE_TEXT), size=10, color=GREY)

# --------------------------------------------------------------------------
# Body
# --------------------------------------------------------------------------
main = doc.add_section()
main.page_width, main.page_height = Inches(8.27), Inches(11.69)
for side in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
    setattr(main, side, Inches(0.95))
header_footer(main)
pg = OxmlElement("w:pgNumType")
pg.set(qn("w:start"), "1")
main._sectPr.append(pg)

box = doc.add_table(rows=1, cols=1)
set_table_borders(box)
set_col_widths(box, [6.37])
c = box.cell(0, 0)
set_cell_bg(c, MIST)
set_cell_margins(c, 160, 140, 200, 200)
p = c.paragraphs[0]
pfmt(p, after=6)
r = fmt_run(p.add_run("ABSTRACT"), size=10, color=FOREST, bold=True)
char_spacing(r, 60)
abstracts = [
    "Can biomass-based construction products from Ontario Crown forests reduce greenhouse-gas emissions relative to the mineral products they would displace, and do the same plants raise rural employment and Indigenous community income? This report answers that question for six forest management units. It is an environmental life cycle assessment and an economic impact assessment.",
    "Both assessments are complete at the inventory stage. The carbon question and the economic question are specified, the boundary of each is fixed, and the foreground data already held in FORBIOM-ON and FORBIOM-ABM are assigned to that boundary. The activity scenario is the package taken forward in the utilization study: community plants and hubs in the six units, four supporting rules taken together, and pellet mills only in Trout Lake and Abitibi.",
    "A characterized life-cycle score is not reported. Neither is an indirect or induced economic multiplier. Those two numbers require external datasets that are not in the model record: environmental product declarations for the concrete and steel assemblies that wood would replace, and Statistics Canada input-output multipliers for the supplying industries. Publishing either figure from the factors already in the forest model would present a partial account as a full one.",
    "What this assessment does establish is where a carbon offset could arise, which emissions are already counted, which are not, and which economic benefits are direct effects of the strategies already simulated. Under the package taken forward, rural and northern employment rises from 1,709 to 4,299 full-time jobs and the present value of Indigenous community income from $431 million to $1,838 million, at an undiscounted public cost of about $331 million. Those are direct effects. They are carried forward from the utilization study and are not re-estimated here.",
]
for txt in abstracts:
    p = c.add_paragraph()
    pfmt(p, after=6, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    add_rich(p, txt, size=10.5)

p = doc.add_paragraph()
pfmt(p, before=16, after=4, keep_next=True)
fmt_run(p.add_run("Contents"), size=16, color=FOREST, bold=True, font=HEAD_FONT)
para_border(p, "bottom", 8, GOLD, 3)
p = doc.add_paragraph()
add_field(
    p,
    'TOC \\o "1-1" \\h \\z \\u',
    "Right-click here and choose \u201cUpdate Field\u201d to build the table of contents.",
    color=GREY,
    italic=True,
)
doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

heading1("1", "Purpose")
p = body("The question put to this assessment is whether biomass-based construction products, supplied from the six study units, can reduce greenhouse-gas emissions relative to the mineral products they would displace, and whether the same development raises income and employment beyond the mill gate. The products in view are cross-laminated timber, glulam, and the community panel. Pellets and bioheat are kept in the boundary only where they use residues from those products. They are not treated as construction products.")
footnote(p, "The six units are Trout Lake, Abitibi River, Algoma, Kenora, Nipissing and Algonquin Park, the same set used in the utilization study.")
body("Two standards govern the life-cycle half. ISO 14040 and ISO 14044 set the goal, the scope, the inventory, the impact assessment and the interpretation. EN 15804, with EN 16485 for roundwood and ISO 21930 for construction products, sets the modular boundary used for building products. The economic half is an impact account in the usual sense: direct effects, then the indirect effects in supplying industries, then the induced effects from household spending. Only the direct effects are quantified in this report, and they are taken from work already done.")
p = body("The report is written so that a later characterized score can be dropped into a fixed frame. The frame is the deliverable. A score computed against a different functional unit, or a multiplier applied to a different industry list, would not be comparable with what is specified here.")
footnote(p, "ISO 14044 requires the goal and scope to be fixed before the inventory is interpreted. That is the reason the boundary is reported even though the impact scores are not.")
body("Three findings can already be stated without that later score. First, the only substitution already counted in the forest models is wood heat displacing heating oil; concrete and steel are not in the carbon account of the utilization study. Second, the direct economic benefits of the package taken forward are large relative to doing nothing, and they are already quantified. Third, an offset claim or a provincial GDP claim that used only the factors in this report would be incomplete, and this report refuses that claim.")

heading1("2", "Relation to the forest-sector models")
p = body("FORBIOM-ON allocates harvest, primary manufacture, secondary manufacture and inter-regional shipments for the six units. FORBIOM-ABM asks which of those plants contractors, mills and investors would actually build. Both models carry a carbon account. That account is storage in products, fossil fuel displaced by wood heat, and emissions from harvest, processing and freight. It is the account a planner needs. It is not a life-cycle result for a building.")
footnote(p, "The utilization study states the same limit: forest carbon stock and substitution for concrete and steel are outside that carbon account.")
body("Two terms are missing, and they are the terms that decide whether wood construction is a carbon offset. The first is the carbon in the standing forest that is released, or not grown, because the extra log was cut. The second is the concrete, steel and masonry that are not produced because a mass-timber bay was built instead. Module D of EN 15804 is where the second term sits. Forest carbon sits outside the building product system and has to be added as a separate consequence of the extra harvest. This report names both terms and does not evaluate either of them numerically.")
body("The economic results of the agent model are in the same position. Rural employment, Indigenous community income and public cost under the strategies S0 to S6 are direct effects of harvest and of the new plants. An economic impact report has to say what those direct effects induce in the rest of the provincial economy. That second step is specified in Section 4 and is not calculated.")

heading1("3", "Life cycle assessment")
heading3("Goal")
body("The goal is to evaluate the carbon-offset potential of biomass-based construction products supplied from the six units, on a basis that can later be compared with a functionally equivalent concrete or steel assembly. The audience is the Province and the technical readers of the utilization study. The assessment is attributional for the product system that is built, and consequential only for the two differences that define an offset: the change in forest carbon, and the displaced mineral product. No comparative assertion for public disclosure under ISO 14044 is made, because the impact assessment has not been completed and no critical review has been commissioned.")

heading3("Functional unit")
p = body("The functional unit is one cubic metre of structural cross-laminated timber or glulam, manufactured from lumber sawn in the six units, delivered to a building site in the Greater Toronto Area or used in northern housing, and providing an equivalent structural function to a reference concrete or steel assembly over a 60-year study period. The reference flow on the wood side is the lumber requirement already used in both models: 1.20 cubic metres of lumber per cubic metre of CLT, and 1.10 per cubic metre of glulam. Community panels are assessed on the same logic per cubic metre of panel, with a lumber requirement of 1.15.")
footnote(p, "Lumber requirements are the FORBIOM-ON parameters lumberInputPerUnit. The 60-year period is the study period adopted here, in line with EN 15978 for buildings. It is not an observed service life.")
body("A cubic metre of product is the right unit for the mill. It is the wrong unit for an offset, which is a difference between two buildings. The comparison therefore has a second functional unit waiting on the reference assemblies: one structural bay of defined span, load and fire rating. That bay is not specified as a bill of materials in this report. Until it is, no claim of the form \u201cone cubic metre of CLT avoids a stated mass of concrete\u201d is available, and none is made.")

heading3("System boundary")
body("Table 1 is the boundary. A module marked \u201cinventory held\u201d can be calculated from factors already in the forest models, once an activity level is chosen. A module marked \u201cnot in the record\u201d cannot. The carbon-offset potential of the product is the sum of the fossil and biogenic terms inside this boundary, minus the same terms for the reference assembly, plus the forest-carbon consequence of the extra harvest. The last two of those three pieces are the ones not in the record.")
caption("Table 1. System boundary for the construction-product assessment.")
simple_table(
    ["Module", "What it covers", "Status in this assessment"],
    [
        ["A1", "Harvest, forwarding, and the standing-forest carbon consequence of the extra cut", "Harvest emissions held; forest carbon not in the record"],
        ["A2", "Haul from stump to mill", "Factor held; applied only inside the unit"],
        ["A3", "Sawmilling and manufacture of CLT, glulam or panels, including residues", "Process factors held"],
        ["A4", "Delivery to the building site", "Freight factor held for shipments already represented"],
        ["A5", "Erection, fixings, and site waste", "Not in the record"],
        ["B", "Use, maintenance, repair and replacement over 60 years", "Not in the record"],
        ["C", "Deconstruction, transport of waste, and end of life", "Not in the record"],
        ["D", "Displaced concrete or steel, and energy or material recovered at end of life", "Not in the record"],
    ],
    [0.85, 3.15, 2.37],
)
body("Biogenic carbon is reported separately from fossil greenhouse gases, following EN 16485 and ISO 21930. Storage in the product is not subtracted from fossil emissions inside a single indicator in this assessment. A net offset would require that subtraction together with Module D and the forest term, and would have to state the timing. A cubic metre stored in a building for 60 years is not the same physical result as a cubic metre whose carbon is credited in the year of harvest.")

heading3("Foreground inventory")
p = body("Table 2 lists the factors carried forward from FORBIOM-ON. They are the foreground emission and storage factors for modules A1 to A4 on the wood side. They are not life-cycle impact scores. Applying them to a harvest volume produces the partial account the forest model already reports. It does not produce an offset against a mineral building.")
footnote(p, "Process and storage factors are the 2020 product parameters in FORBIOM-ON. Harvest and freight factors are those used in the agent model. Bioheat displacement is included because it is the only substitution the existing account already contains.")
caption("Table 2. Foreground factors carried forward. Not life-cycle results.")
simple_table(
    ["Flow", "Factor", "Role in the boundary"],
    [
        ["CLT, process emissions", "0.150 tCO\u2082 / m\u00B3", "Module A3, fossil"],
        ["CLT, carbon storage", "0.70 tCO\u2082 / m\u00B3", "Biogenic, reported separately"],
        ["Glulam, process emissions", "0.170 tCO\u2082 / m\u00B3", "Module A3, fossil"],
        ["Glulam, carbon storage", "0.70 tCO\u2082 / m\u00B3", "Biogenic, reported separately"],
        ["Lumber, process emissions", "0.065 tCO\u2082 / m\u00B3", "Module A3, primary"],
        ["Lumber, carbon storage", "0.40 tCO\u2082 / m\u00B3", "Biogenic, reported separately"],
        ["Harvest", "0.012 tCO\u2082 / m\u00B3", "Module A1, fossil"],
        ["Freight", "0.00005 tCO\u2082 / m\u00B3\u00B7km", "Modules A2 and A4"],
        ["Bioheat displacing oil", "1.23 tCO\u2082e / odt", "The only substitution already counted"],
    ],
    [2.15, 1.7, 2.52],
)
body("Activity levels, if a later score is computed, should be taken from the same runs as the economic account so that the two assessments describe one future. The utilization study reports, under the package taken forward, a late-period utilization of 65.7 percent of the long-term managed harvest against 40.7 percent with no new plants, and a cumulative harvest of 60.8 million cubic metres over 2026\u20132045 against 42.3. Those volumes are the candidate activity data. They are not multiplied by the factors in Table 2 in this report, because that product would be mistaken for the offset.")

heading3("Carbon-offset potential")
body("The offset potential is defined here, and left unevaluated, as three differences. First, fossil emissions of the wood product system minus fossil emissions of the reference concrete or steel assembly, over the same bay and the same 60 years. Second, biogenic carbon held in the wood product and in any wood residue that remains in use, reported on its own line and not netted against the first difference. Third, the change in carbon in the standing forest caused by cutting the extra log, including the regrowth that follows. A result that contains only the second difference is a storage account. A result that contains the first and the second, but not the third, is a building account with an open forest boundary. Neither is the offset potential named in the purpose of this assessment.")
body("The reference assembly is the missing dataset. An environmental product declaration for a Canadian concrete and a Canadian steel assembly of the same structural function would close Module D. A forest-carbon module linked to the extra harvest, by unit and by species, would close the third difference. Poplar and tolerant hardwood are a large share of the unused managed volume and are barely used by the softwood mass-timber plants. An offset calculated on softwood CLT alone would not describe those cubic metres.")

heading3("Impact categories")
body("The category required for the carbon question is global warming, split into fossil, biogenic and land-use change, over 100 years. No other category is required to answer the question as posed. Acidification, eutrophication, smog and particulate matter are part of a complete construction-product declaration under EN 15804 and would be added if a declaration is later prepared. They are listed so the boundary does not have to be reopened. They are not evaluated.")

heading3("Data required before a score")
body("Closing the score does not require a change to this boundary. It requires six external items, each tied to a module that Table 1 marks as not in the record. They are listed so the next measurement has an owner and a place to land.")
bullet("**Reference assemblies.** A bill of materials for one concrete bay and one steel bay of the same span, load and fire rating as the wood bay, with Canadian environmental product declarations or an equivalent public inventory. This fills Module D.")
bullet("**Site works.** Crane time, fixings, membranes and the share of product wasted at the site, for the wood bay and for each reference bay. This fills Module A5. Without it, a mill-gate comparison is being asked to stand in for a building.")
bullet("**Use and end of life.** Replacement of finishes and connectors over 60 years, and a stated fate for the wood at demolition: reuse, recycling, landfill or combustion. This fills Modules B and C. The fate decides whether the storage factor in Table 2 is still present at year 60.")
bullet("**Forest carbon.** A unit-level account of the carbon stock change caused by the extra harvest, by softwood, poplar and hardwood, including regrowth. The managed-volume figures already used for utilization are not that account.")
bullet("**Adhesives and connectors.** Resin mass per cubic metre of CLT and glulam, and the steel in plates and screws. These are fossil flows inside Module A3 that the roundwood factors in Table 2 do not contain.")
bullet("**Timing.** The year of each emission and each storage flow, so that a later user can discount or not. This report does not apply a carbon discount rate.")
body("Until those six items are in hand, the honest statement of the carbon-offset potential is the definition in this section, not a tonne figure. The economic account has an analogous missing item, the multiplier, treated in Section 4.")

heading1("4", "Economic impact")
heading3("Direct effects")
p = body("The direct effects are the jobs, the income and the public cost that arise in the six units and in the plants the strategies allow. Table 3 carries them forward from the utilization study for the reference case and for the package taken forward. They are means under the central demand case. They are not an input-output result, and they are not revised in this report.")
footnote(p, "Source: provincial means in the utilization study. Income is a present value at 4 percent. Jobs are full-time equivalents late in the horizon, excluding the Greater Toronto Area. Public cost is cumulative grants and programme cost.")
caption("Table 3. Direct effects carried forward. Not indirect or induced impacts.")
simple_table(
    ["", "No new plants", "Package taken forward"],
    [
        ["Rural and northern jobs", "1,709", "4,299"],
        ["Indigenous community income", "$431 million", "$1,838 million"],
        ["Public cost", "0", "$331 million"],
        ["New plants losing money", "\u2014", "1.5 percent"],
    ],
    [2.5, 1.9, 1.97],
)
body("The income figure is wages, contractor margins and the equity share of plant profits, accruing to Indigenous communities. It is not a measure of provincial gross domestic product. The job figure excludes the urban mass-timber plants, which buy lumber and do not add harvest. Public cost is the outlay side of the same strategies. A benefit that ignores it is incomplete even before indirect effects are considered.")

heading3("Accounts specified and not estimated")
body("Table 4 is the economic impact account. The direct column is filled by Table 3. The indirect column would apply Statistics Canada input-output multipliers, or a supply-use model of Ontario, to the purchases of the new mills: logs, energy, resins, transport, professional services and maintenance. The induced column would apply the household-spending block to the wages in the direct and indirect columns. Neither multiplier is in the project record. Inventing a round factor, or borrowing one from another province and another year, would give a number this assessment could not defend.")
caption("Table 4. Economic impact account. Only the direct column is quantified.")
simple_table(
    ["Channel", "What it measures", "Status"],
    [
        ["Direct output", "Harvest, lumber, mass timber, panels, residues sold", "Activity data held; not valued as GDP"],
        ["Direct jobs and income", "Table 3", "Quantified"],
        ["Direct public cost", "Table 3", "Quantified"],
        ["Indirect", "Output and jobs in industries supplying the new plants", "Not estimated"],
        ["Induced", "Output and jobs from spending of the new wages", "Not estimated"],
        ["Tax", "Provincial income, corporate and commodity tax on the three columns", "Not estimated"],
        ["Distribution", "Share of direct income in Indigenous and rural households", "Quantified for Indigenous income"],
    ],
    [1.45, 3.15, 1.77],
)
body("The industry list to which a later multiplier must be applied is forestry and logging, sawmilling, engineered-wood manufacture, construction, and truck and rail transport. Resin and connector manufacture matters for CLT and glulam and is not an Ontario forest industry; it belongs in the indirect column, not in the direct forest account. Construction-site jobs belong to module A5 of the life-cycle boundary and to the direct column of the economic account only to the extent that the wood building changes site labour relative to the reference building. That difference is not estimated.")

heading3("Public cost and the benefit")
body("The economic benefit relevant to the Province is not the gross income in Table 3. It is that income, and any indirect and induced income later estimated, net of the public cost of grants, training and the heat payment, and net of any displacement of existing mills. The agent model already allows incumbent mills to exit after sustained losses. A gross job count that adds new-plant jobs and ignores exits would double-count the employment benefit. The figures in Table 3 are net of the exits the model produced. They should be kept on that basis when the indirect column is filled.")

heading3("How the multiplier would be applied")
body("When a Statistics Canada table is available, the indirect column is not a single factor applied to the whole of Table 3. The direct output has to be split by purchasing industry first. A hub buys logs, energy, resin, steel connectors, transport and maintenance in different proportions from a bioheat plant, and a pellet mill buys almost none of the construction-side inputs. One multiplier for \u201cforestry\u201d applied to jobs or to income would assign the sawmill\u2019s suppliers to the wrong industries.")
body("The practical sequence is fixed here so that the later arithmetic does not have to be redesigned. Classify each new plant in the package taken forward as a hub, a spoke, a bioheat plant or a pellet mill. Take its purchases from the cost structure already used to decide whether the plant is built: log purchases valued at the delivered cost, energy, freight, and the non-wood capital items. Map those purchases onto the supply-use industries. Apply the open-model multipliers for indirect effects. Apply the closed-model, household-endogenous multipliers only for the induced column, and show the two columns separately. Subtract the public cost in Table 3 after the gross effects, not before, and do not multiply the public cost by an employment factor. A grant is a transfer. Treating it as an output of the construction industry would invent a second benefit from the same dollar.")
body("Imports are a leakage. Resin, connectors and any machinery not made in Ontario leave the province at the first purchase. They belong in the direct cost of the plant and they do not belong in the Ontario indirect column. The same rule applies to mass timber sold into the Greater Toronto Area: the income from that sale is Ontario income only to the extent that the manufacture and the haul occurred in Ontario. The urban plant that buys lumber and adds no harvest was already excluded from the rural job count for this reason, and it should stay out of a northern impact total.")
body("Nothing in that sequence produces a number until the multiplier table and the purchase split are both present. The sequence is part of the completed assessment because it decides what will count as a benefit. A later report that uses a different sequence is a different assessment, not an update of this one.")

heading1("5", "Joint reading")
body("The two assessments describe one physical future and must use one activity level. The life-cycle inventory should be driven by the harvest, the product mix and the haul distances of the same strategy whose jobs and income are in the economic account. Mixing the planner\u2019s allocation from FORBIOM-ON with the plants the agents actually build would give a carbon figure for a mill that was not constructed and an income figure for a mill that was.")
body("Three results are then readable together, and only together. The fossil and biogenic lines of the life-cycle account say what the products cost and store in carbon terms. The forest-carbon line says whether the extra cut is repaid by regrowth inside the study period. The economic account says who is paid, at what public cost, to produce that carbon result. An offset that appears only because a high displacement factor was assumed, and that is attached to a strategy whose new plants lose money, is not a result this assessment would carry forward. Equally, a large income gain attached to a strategy that leaves hardwood unused is not a full use of the managed volume.")
body("The package taken forward in the utilization study is the activity scenario this assessment is built to receive: hubs, community plants and bioheat in all six units, the four supporting rules, and pellet mills only where they earned a place. This report does not reopen that choice. It fixes the questions that have to be answered before that package can be described as a carbon offset or as a provincial economic impact.")

heading1("6", "What was completed")
body("This report is an environmental life cycle assessment and an economic impact assessment of the carbon-offset potential and the economic benefits of biomass-based construction products. The work completed is the following.")
bullet("The goal, the functional unit, the reference flow and the decision not to make a public comparative assertion.")
bullet("The modular system boundary, with each module marked as inventory held or not in the record (Table 1).")
bullet("The foreground emission, storage and freight factors assigned to that boundary (Table 2), carried from the forest models without being converted into an offset.")
bullet("A definition of carbon-offset potential as three differences: fossil emissions against the reference assembly, biogenic storage reported separately, and the forest-carbon consequence of the extra harvest.")
bullet("The direct economic effects of the reference case and of the package taken forward (Table 3), and the indirect, induced and tax columns specified and left empty (Table 4).")
bullet("The six external items required before a characterized score can be computed: reference assemblies, site works, use and end of life, forest carbon, adhesives and connectors, and the timing of flows.")
p = body("What was not completed, and is stated as such, is the characterized global-warming score and the indirect economic impact. The missing inputs are an environmental product declaration, or an equivalent bill of materials, for the reference concrete and steel assemblies, and a current Statistics Canada multiplier for the industry list in Section 4. Those inputs are external to the forest models. They are the next measurement, not a gap in the boundary.")
footnote(p, "A critical review under ISO 14044 would be required before any comparative result from that next measurement was disclosed to the public. This report does not request that review, because there is no comparative result to review.")
body("The finished frame is a carbon account that can accept a later building comparison without changing its modules, and an economic account that already holds the direct benefits of the recommended utilization package and that is ready for a multiplier when one is available. Nothing below that frame is invented in this report.")

heading1("7", "Limits")
body("The six units are not Ontario. Volumes, jobs and income in Table 3 must not be scaled to the provincial harvest by a constant. Logs do not move between units in the agent model, and Kenora and Trout Lake have no western or export market, so haul in the inventory is shorter than the haul a plant in those units may in fact use.")
body("Hardwood and poplar engineered products are not in the product system. Any offset or income figure later computed from Table 2 applies to softwood CLT, glulam and the panel, not to the unused hardwood managed volume.")
body("Carbon storage factors credit the product. They do not describe the year in which the forest regrows, and they do not survive if the building is demolished and the wood is burned inside the study period. Module C is empty for that reason. Filling it with an assumption that all stored carbon remains stored would decide the offset in advance.")
body("The direct income and job figures depend on housing need, heat load, prices and grant rates that the utilization study already treated as assumptions. A change in those assumptions that left the strategy ranking intact can still change the dollars in Table 3. The economic impact account should be recomputed, not rescaled, if those assumptions are replaced.")
body("Nothing in this report is a life-cycle result for a building, a carbon-offset credit, or a provincial GDP impact.")

p = doc.add_paragraph()
pfmt(p, before=14, after=2)
fmt_run(p.add_run("References for the method"), size=12, color=FOREST, bold=True, font=HEAD_FONT)
for ref in [
    "ISO 14040:2006 and ISO 14044:2006. Environmental management \u2014 Life cycle assessment.",
    "EN 15804. Sustainability of construction works \u2014 Core rules for environmental product declarations.",
    "EN 16485. Round and sawn timber \u2014 Environmental product declarations \u2014 Product category rules.",
    "ISO 21930. Sustainability in buildings and civil engineering works \u2014 Core rules for environmental product declarations of construction products and services.",
    "EN 15978. Sustainability of construction works \u2014 Assessment of environmental performance of buildings.",
]:
    bullet(ref)

# ---- Code, data and appendix ----
p = doc.add_paragraph()
pfmt(p, before=16, after=4, keep_next=True)
fmt_run(p.add_run("Code, data and scripts"), size=11, color=FOREST, bold=True, italic=True, font=HEAD_FONT)
box = doc.add_table(rows=1, cols=1)
set_table_borders(box)
set_col_widths(box, [6.37])
bc = box.cell(0, 0)
set_cell_bg(bc, MIST)
set_cell_margins(bc, 140, 120, 180, 180)
items = [
    ("GitHub repository", None),
    ("Methods paper", "docs/LCA_Economic_Impact_Methods_and_Data.md (and .docx): goal, boundary, factors, economic account and data sources."),
    ("Report builder", "scripts/build_lca_econ_report_docx.py regenerates this DOCX."),
    ("Utilization results", "abm/results/provincial_base.csv and related tables supply the direct effects in Table 3."),
]
for i, (lab, txt) in enumerate(items):
    p = bc.paragraphs[0] if i == 0 else bc.add_paragraph()
    pfmt(p, after=4 if i < len(items) - 1 else 0, left=1.0, first=-1.0)
    p.paragraph_format.tab_stops.add_tab_stop(Inches(1.35))
    fmt_run(p.add_run(lab), color=FOREST, bold=True)
    p.add_run("\t")
    if i == 0:
        add_rich(p, "Full package (models, derived data, reports): ")
        add_hyperlink(p, GITHUB_URL, GITHUB_URL, size=10.5)
        add_rich(p, ".")
    else:
        add_rich(p, txt, size=10.5)

heading1("A", "Repository")
p = body("The public repository that accompanies this report holds the model code, the derived tables, the methods paper and this assessment. It does not hold the raw ministry extracts, the inventory geodatabases, or working files from the project archive. ")
add_hyperlink(p, GITHUB_URL, GITHUB_URL, size=11)
add_rich(p, ".")

heading3("Contents")
simple_table(
    ["Path", "Contents"],
    [
        ["`report/`", "Assessment DOCX (this report) and the utilization study"],
        ["`docs/`", "Methods-and-data paper (Markdown and DOCX); appendix guide"],
        ["`abm/`", "Agent-based model, calibration CSVs, provincial and regional result tables"],
        ["`gams/`", "Planning-model source and bridge scripts"],
        ["`scripts/`", "Builders for this report and the methods paper"],
        ["`data/`", "Model-ready CSV inputs and GAMS summary outputs"],
        ["`README.md`", "Overview, quick start and citation"],
    ],
    [1.55, 4.82],
    size=8.5,
)

heading3("Reproduction")
bullet(f"**Methods paper:** `docs/LCA_Economic_Impact_Methods_and_Data.md` "
       f"(regenerate DOCX with `scripts/build_lca_methods_paper_docx.py`).")
bullet(f"**This report:** `scripts/build_lca_econ_report_docx.py` "
       "(Python 3.11+, `python-docx`; Microsoft Word optional to refresh the TOC).")
bullet("**Direct effects in Table 3:** means from `abm/results/provincial_base.csv`, strategies S0 and S6, "
       "carried forward from the utilization study; not re-estimated here.")
bullet("**Foreground factors in Table 2:** planning-model product parameters and agent-model harvest, freight "
       "and bioheat factors, documented in the methods paper.")

heading3("Redistribution")
bullet("**Included:** derived calibration CSVs, summary result tables, model source, this report, the methods paper.")
bullet("**Not redistributed:** raw ARWoodS/eFAR extracts (Ontario MNR), FRI geodatabases, large GDX binaries.")
bullet("**Status:** characterized life-cycle scores and input-output multipliers are specified and left empty on purpose.")

heading3("Citation")
body("Yousefpour, R. & Elfahli, Y. (2026). *Environmental life cycle assessment and economic impact of "
     "biomass-based construction products* (inventory stage). Methods and data: "
     f"`docs/LCA_Economic_Impact_Methods_and_Data.md`. Code and data package: {GITHUB_URL}.")

doc.save(OUT)
print("Saved", OUT)
print("GitHub URL used:", GITHUB_URL)
