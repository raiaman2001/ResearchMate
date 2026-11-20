"""Report export: Markdown -> DOCX / PDF (English aur Hindi/Devanagari dono).

PDF: fpdf2 + bundled Noto Sans (Latin) + Noto Sans Devanagari + text shaping (HarfBuzz) taaki matras/संयुक्त अक्षर
sahi bane. DOCX: python-docx, complex-script fonts set (Word/LibreOffice Devanagari sahi dikhate hain).
"""
import io
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from app import config
from app.lang import DEVA_RE


class ExportError(Exception):
    """User ko dikhane layak message (jaise font missing)."""


# ======================= markdown parsing (DOCX aur PDF dono ke liye) =======================
@dataclass
class Block:
    kind: str                       # h1 h2 h3 p bullet number hr
    spans: list = field(default_factory=list)      # [(text, style)] style: "" "b" "i" "bi" "code"
    level: int = 0
    num: int | None = None


INLINE_RE = re.compile(r"\*\*(?P<b>.+?)\*\*|`(?P<c>[^`]+)`|(?<![\*\w])\*(?P<i>[^\s*][^*]*?)\*(?![\*\w])")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
HR_RE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
BULLET_RE = re.compile(r"^(\s*)[-*•]\s+(.*)$")
NUMBER_RE = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
URL_RE = re.compile(r"https?://[^\s<>()\[\]]+[^\s<>()\[\].,;:!?।]")


def _merge(a, b):
    return "".join(sorted(set(a + b)))


def parse_inline(text, base=""):
    """**bold**, *italic*, `code` ko [(text, style)] me todta hai (nested ok)."""
    spans, pos = [], 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            spans.append((text[pos:m.start()], base))
        if m.group("b") is not None:
            spans += parse_inline(m.group("b"), _merge(base, "b"))
        elif m.group("c") is not None:
            spans.append((m.group("c"), "code"))
        else:
            spans += parse_inline(m.group("i"), _merge(base, "i"))
        pos = m.end()
    if pos < len(text):
        spans.append((text[pos:], base))
    return [(t, s) for t, s in spans if t]


def split_urls(text):
    """[(segment, is_url)]: URLs ko alag karo (clickable link ke liye)."""
    out, pos = [], 0
    for m in URL_RE.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], False))
        out.append((m.group(0), True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    return out


def plain(spans):
    return "".join(t for t, _ in spans)


CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_control(s):
    """Control characters DOCX (XML) aur PDF dono ko tod dete hain."""
    return CTRL_RE.sub("", s)


def parse_markdown(md):
    md = strip_control(md or "")
    blocks, para = [], []

    def flush():
        if para:
            blocks.append(Block("p", parse_inline(" ".join(x.strip() for x in para))))
            para.clear()

    for raw in md.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            flush()
        elif (m := HEADING_RE.match(line)):
            flush()
            blocks.append(Block(f"h{min(len(m.group(1)), 3)}", parse_inline(m.group(2).strip())))
        elif HR_RE.match(line):
            flush()
            blocks.append(Block("hr"))
        elif (m := BULLET_RE.match(line)):
            flush()
            blocks.append(Block("bullet", parse_inline(m.group(2)), level=min(len(m.group(1)) // 2, 2)))
        elif (m := NUMBER_RE.match(line)):
            flush()
            blocks.append(Block("number", parse_inline(m.group(3)), level=min(len(m.group(1)) // 2, 2), num=int(m.group(2))))
        else:
            para.append(line)
    flush()
    return blocks


def needs_devanagari(md):
    return bool(DEVA_RE.search(md))


# ======================= DOCX =======================
CS_FONT = "Nirmala UI"          # Windows ka Devanagari font; Word/LibreOffice missing ho to khud fallback lete hain


def _set_cs(rpr, size_pt=None, bold=None, italic=None):
    """Complex-script (Devanagari) ke liye font/size/bold alag XML attributes se hote hain."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    fonts.set(qn("w:cs"), CS_FONT)
    for tag, val in (("w:szCs", None if size_pt is None else str(int(size_pt * 2))),
                     ("w:bCs", "1" if bold else None), ("w:iCs", "1" if italic else None)):
        if val is not None and rpr.find(qn(tag)) is None:
            el = OxmlElement(tag)
            if tag == "w:szCs":
                el.set(qn("w:val"), val)
            rpr.append(el)


def _add_hyperlink(paragraph, url, text, bold=False):
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    r_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    for tag, attrs in (("w:color", {"w:val": "0563C1"}), ("w:u", {"w:val": "single"})):
        el = OxmlElement(tag)
        for k, v in attrs.items():
            el.set(qn(k), v)
        rpr.append(el)
    if bold:
        rpr.append(OxmlElement("w:b"))
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    h.append(run)
    paragraph._p.append(h)


def _add_spans(paragraph, spans, base_bold=False):
    for text, style in spans:
        for seg, is_url in split_urls(text):
            if is_url:
                _add_hyperlink(paragraph, seg, seg, bold="b" in style or base_bold)
                continue
            run = paragraph.add_run(seg)
            bold, italic = "b" in style or base_bold, "i" in style
            run.bold, run.italic = bold or None, italic or None
            if style == "code":
                run.font.name = "Consolas"
            _set_cs(run._r.get_or_add_rPr(), bold=bold, italic=italic)


def _hr(paragraph):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    ppr = paragraph._p.get_or_add_pPr()
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "999999")):
        bottom.set(qn(k), v)
    border.append(bottom)
    ppr.append(border)


def _page_number_footer(section):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("ResearchMate · ")
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "1"
    run.append(t)
    fld.append(run)
    p._p.append(fld)


def to_docx(markdown, title=None):
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    blocks = parse_markdown(markdown)
    doc = Document()
    sizes = {"Normal": 11, "Title": 22, "Heading 1": 18, "Heading 2": 14, "Heading 3": 12,
             "List Bullet": 11, "List Bullet 2": 11, "List Bullet 3": 11}
    for name, size in sizes.items():                                    # har style me Devanagari font/size
        st = doc.styles[name]
        if name == "Normal":
            st.font.name, st.font.size = "Calibri", Pt(size)
        is_heading = name.startswith(("Heading", "Title"))
        if is_heading:
            st.font.bold = True                       # Latin aur Devanagari dono bold (mismatch na ho)
        rpr = st.element.get_or_add_rPr()
        _set_cs(rpr, size_pt=size, bold=is_heading)
    lang = OxmlElement("w:lang")                                         # complex-script language = Hindi
    lang.set(qn("w:val"), "en-US")
    lang.set(qn("w:bidi"), "hi-IN")
    doc.styles["Normal"].element.get_or_add_rPr().append(lang)

    first_h1, heading_title = True, None
    for b in blocks:
        if b.kind == "h1":
            text = plain(b.spans)
            heading_title = heading_title or text
            p = doc.add_paragraph(style="Title" if first_h1 else "Heading 1")
            first_h1 = False
            _add_spans(p, b.spans)
        elif b.kind in ("h2", "h3"):
            p = doc.add_paragraph(style="Heading 2" if b.kind == "h2" else "Heading 3")
            _add_spans(p, b.spans)
        elif b.kind == "bullet":
            style = "List Bullet" if b.level == 0 else f"List Bullet {b.level + 1}"
            _add_spans(doc.add_paragraph(style=style), b.spans)
        elif b.kind == "number":
            # Word ki auto-numbering lists ke beech continue ho jati hai: isliye literal number + hanging indent
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.3 + 0.25 * b.level)
            p.paragraph_format.first_line_indent = Inches(-0.3)
            p.add_run(f"{b.num}.\t")
            _add_spans(p, b.spans)
        elif b.kind == "hr":
            _hr(doc.add_paragraph())
        else:
            _add_spans(doc.add_paragraph(), b.spans)

    _page_number_footer(doc.sections[0])
    cp = doc.core_properties
    cp.title = title or heading_title or "Research report"
    cp.author = "ResearchMate"
    cp.language = "hi-IN" if needs_devanagari(markdown) else "en-US"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ======================= PDF =======================
EMOJI_MAP = [("✅", "[OK]"), ("⚠️", "[!]"), ("⚠", "[!]"), ("❌", "[X]"), ("✓", "[OK]"), ("→", "->")]
EMOJI_STRIP = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")


def pdf_text(s):
    """Noto Sans me emoji/arrows nahi hote: short text tags me badlo, baaki hata do."""
    for a, b in EMOJI_MAP:
        s = s.replace(a, b)
    return EMOJI_STRIP.sub("", s)


def _fonts():
    d = config.PDF_FONT_DIR
    need = {"latin": ["NotoSans-Regular.ttf", "NotoSans-Bold.ttf"],
            "deva": ["NotoSansDevanagari-Regular.ttf", "NotoSansDevanagari-Bold.ttf"]}
    return {k: all((d / f).exists() for f in v) for k, v in need.items()}, d


def to_pdf(markdown, title=None):
    from fpdf import FPDF

    deva = needs_devanagari(markdown)
    have, fdir = _fonts()
    if deva and not (have["latin"] and have["deva"]):
        raise ExportError(
            f"Hindi PDF ke liye Noto Sans aur Noto Sans Devanagari fonts chahiye (folder: {fdir}). "
            "PDF_FONT_DIR set karo ya static/fonts me fonts rakho. Tab tak DOCX export use kar sakte ho.")
    if deva:
        try:
            import uharfbuzz  # noqa: F401
        except ImportError as e:
            raise ExportError("Hindi PDF ke liye `pip install uharfbuzz` chahiye (text shaping).") from e

    class ReportPDF(FPDF):
        def footer(self):
            self.set_y(-12)
            self.set_font(FAMILY, "", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, f"ResearchMate · {self.page_no()}/{{nb}}", align="C")

    pdf = ReportPDF(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, 18)
    pdf.alias_nb_pages()
    if have["latin"]:
        FAMILY = "Body"
        pdf.add_font("Body", "", str(fdir / "NotoSans-Regular.ttf"))
        pdf.add_font("Body", "B", str(fdir / "NotoSans-Bold.ttf"))
    else:                                            # fonts nahi: English ke liye core font (latin-1 tak)
        FAMILY = "Helvetica"
    if have["deva"]:
        pdf.add_font("Dev", "", str(fdir / "NotoSansDevanagari-Regular.ttf"))
        pdf.add_font("Dev", "B", str(fdir / "NotoSansDevanagari-Bold.ttf"))
        pdf.set_fallback_fonts(["Dev"])
    if deva:
        pdf.set_text_shaping(True)                   # matras / conjuncts sahi jodne ke liye

    def clean(t):
        t = pdf_text(t)
        return t if have["latin"] else t.encode("latin-1", "replace").decode("latin-1")

    def font(style="", size=10.5):
        pdf.set_font(FAMILY, style, size)

    def write_spans(spans, h, base_bold=False, color=(30, 30, 30)):
        for text, style in spans:
            muted = "i" in style
            font("B" if ("b" in style or base_bold) else "")
            for seg, is_url in split_urls(text):
                if is_url:
                    pdf.set_text_color(5, 99, 193)
                    pdf.write(h, clean(seg), link=seg)
                else:
                    pdf.set_text_color(*((110, 110, 110) if muted else color))
                    pdf.write(h, clean(seg))

    blocks = parse_markdown(markdown)
    heading_title = next((plain(b.spans) for b in blocks if b.kind == "h1"), None)
    pdf.set_title(clean(title or heading_title or "Research report"))
    pdf.set_author("ResearchMate")
    pdf.set_creator("ResearchMate")
    try:
        pdf.set_lang("hi" if deva else "en")
    except Exception:
        pass
    pdf.add_page()

    H = 6.2
    for b in blocks:
        base = pdf.l_margin
        if b.kind in ("h1", "h2", "h3"):
            size = {"h1": 18, "h2": 14, "h3": 12}[b.kind]
            pdf.ln(3 if b.kind != "h1" else 0)
            font("B", size)
            pdf.set_text_color(20, 20, 20)
            pdf.multi_cell(0, size * 0.55, clean(plain(b.spans)).strip(), new_x="LMARGIN", new_y="NEXT")   # emoji hatne ke baad bacha space
            pdf.ln(1.5)
        elif b.kind == "hr":
            y = pdf.get_y() + 2
            pdf.set_draw_color(180, 180, 180)
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(5)
        elif b.kind in ("bullet", "number"):
            indent = 4 + 5 * b.level
            mw = 5 if b.kind == "bullet" else 7
            font("")
            pdf.set_text_color(30, 30, 30)
            pdf.set_x(base + indent)
            pdf.cell(mw, H, "•" if b.kind == "bullet" else f"{b.num}.")
            pdf.set_left_margin(base + indent + mw)          # wrap hone par hanging indent
            pdf.set_x(base + indent + mw)
            write_spans(b.spans, H)
            pdf.ln(H + 1)
            pdf.set_left_margin(base)
        else:
            write_spans(b.spans, H)
            pdf.ln(H + 2)
    return bytes(pdf.output())


# ======================= public API =======================
FORMATS = {
    "md": ("text/markdown; charset=utf-8", "md"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "pdf": ("application/pdf", "pdf"),
}


def export_report(markdown, fmt, title=None):
    """(bytes, mime, extension). Galat format par ValueError, font/library missing par ExportError."""
    if fmt not in FORMATS:
        raise ValueError(f"Unknown format: {fmt} (md/docx/pdf)")
    mime, ext = FORMATS[fmt]
    if fmt == "md":
        return markdown.encode("utf-8"), mime, ext
    data = to_docx(markdown, title) if fmt == "docx" else to_pdf(markdown, title)
    return data, mime, ext


def download_filename(title, ext, limit=60):
    """Unicode-safe filename: (ascii fallback, utf-8 percent-encoded) -> Content-Disposition ke liye."""
    stem = re.sub(r"[^\w\u0900-\u097F\-]+", "_", (title or "report"), flags=re.UNICODE).strip("_")[:limit] or "report"
    return f"report.{ext}", f"{quote(stem)}.{ext}", f"{stem}.{ext}"


def content_disposition(title, ext):
    ascii_name, encoded, _ = download_filename(title, ext)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"
